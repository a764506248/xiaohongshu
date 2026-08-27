import hashlib
import io
import json
import re
import textwrap
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.models import (
    Article, ArticleVersion, ContentTask, ImagePage, ImageVersion, TaskStatus, XiaohongshuPackage,
)
from app.aliyun_models import default_image_model, generate_image
from app.core.config import get_settings

STORAGE_ROOT = Path(__file__).resolve().parents[1] / "storage" / "images"
FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


class LocalImageProvider:
    width = 1080
    height = 1440

    @staticmethod
    def font(size: int, bold: bool = False):
        for candidate in FONT_CANDIDATES:
            if Path(candidate).exists():
                try:
                    return ImageFont.truetype(candidate, size=size, index=1 if bold else 0)
                except OSError:
                    continue
        return ImageFont.load_default()

    @staticmethod
    def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for char in text.replace("\n", " "):
            candidate = current + char
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines

    def render(self, page: ImagePage, output_path: Path) -> tuple[str, int, int]:
        palettes = {
            "editorial": ("#F3F0E7", "#20211F", "#EF5B3F", "#DDD8C9"),
            "dark": ("#171918", "#F5F2E9", "#7DDBAF", "#343936"),
            "warm": ("#F7E7DA", "#422D25", "#D55038", "#EBCBB8"),
        }
        bg, ink, accent, line = palettes.get(page.template, palettes["editorial"])
        image = Image.new("RGB", (self.width, self.height), bg)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((70, 70, 1010, 1370), radius=36, outline=line, width=3)
        draw.rounded_rectangle((90, 92, 270, 146), radius=27, fill=accent)
        label_font = self.font(27, bold=True)
        draw.text((122, 104), f"PAGE {page.page_number:02d}", font=label_font, fill="#FFFFFF")
        title_font = self.font(70, bold=True)
        body_font = self.font(38)
        foot_font = self.font(26)
        title_lines = self.wrap(draw, page.title, title_font, 820)[:4]
        y = 250
        for title_line in title_lines:
            draw.text((120, y), title_line, font=title_font, fill=ink)
            y += 96
        draw.rectangle((120, y + 12, 260, y + 22), fill=accent)
        y += 85
        body_lines = self.wrap(draw, page.body, body_font, 820)[:10]
        for body_line in body_lines:
            draw.text((120, y), body_line, font=body_font, fill=ink)
            y += 62
        draw.text((120, 1290), "AI 应用开发 · 实战分享", font=foot_font, fill=ink)
        draw.text((885, 1290), f"{page.page_number}", font=foot_font, fill=accent)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG", optimize=True)
        digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return digest, self.width, self.height


def find_package(db: Session, task_id: str) -> XiaohongshuPackage | None:
    """查询任务的内容包；尚未生成时返回 None，由调用方决定业务语义。"""
    return db.scalar(
        select(XiaohongshuPackage)
        .options(selectinload(XiaohongshuPackage.pages).selectinload(ImagePage.versions))
        .where(XiaohongshuPackage.content_task_id == task_id)
    )


def get_package(db: Session, task_id: str) -> XiaohongshuPackage:
    """获取必须存在的内容包，供编辑、导出、发布等接口使用。"""
    package = find_package(db, task_id)
    if not package:
        raise HTTPException(404, "小红书内容包尚未生成")
    return package


def _plain(markdown: str) -> str:
    return re.sub(r"[#>*_`]", "", markdown).strip()


def _visual_script(version: ArticleVersion) -> list[dict]:
    sections = re.findall(r"^##\s+(.+?)\n+([\s\S]*?)(?=^##\s+|\Z)", version.content, re.MULTILINE)
    pages = [{"title": version.title[:36], "body": "一份可以直接执行的技术实践指南", "purpose": "封面"}]
    for heading, body in sections[:3]:
        text = _plain(body)
        text = re.sub(r"\s+", " ", text)[:180]
        pages.append({"title": heading[:36], "body": text or "从实际问题出发，逐步验证并记录结果。", "purpose": "核心内容"})
    pages.append({"title": "现在就开始行动", "body": "选择一个真实的小任务，定义输入和输出，用一周完成第一个可用闭环。", "purpose": "行动建议"})
    while len(pages) < 3:
        pages.insert(-1, {"title": "实践要点", "body": _plain(version.content)[:180], "purpose": "内容摘要"})
    return pages[:5]


def render_page(db: Session, page: ImagePage, source_type: str = "generated") -> ImageVersion:
    next_number = (db.scalar(select(func.max(ImageVersion.version_number)).where(ImageVersion.page_id == page.id)) or 0) + 1
    relative = f"{page.package_id}/{page.id}-v{next_number}.png"
    output = STORAGE_ROOT / relative
    settings = get_settings()
    # 自动化测试继续使用确定性的本地渲染；真实环境必须调用模型管理中
    # 已启用的阿里图片模型，不再静默生成一张本地占位海报。
    if settings.app_env == "test":
        digest, width, height = LocalImageProvider().render(page, output)
    else:
        model = default_image_model(db)
        if not model:
            raise HTTPException(503, "没有可用的阿里图片模型，请先在模型管理中启用图片模型")
        api_key = model.api_key or settings.aliyun_model_api_key
        if not api_key:
            raise HTTPException(503, f"阿里图片模型 {model.name} 尚未配置 API Key")
        prompt = (
            "生成一张竖版小红书技术知识卡片，画面比例约为3:4，版式简洁专业，"
            "中文必须清晰可读，不要水印。"
            f"视觉说明：{page.visual_description}。"
            f"页面标题：{page.title}。正文要点：{page.body}。"
            "使用统一的教育科技品牌视觉，保留充分留白和清晰的信息层级。"
        )
        try:
            image_bytes, _, _ = generate_image(model, prompt, api_key=api_key)
        except Exception as exc:
            raise HTTPException(502, f"阿里图片模型 {model.model} 生成失败：{exc}") from exc
        output.parent.mkdir(parents=True, exist_ok=True)
        generated = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        generated.save(output, format="PNG", optimize=True)
        digest, width, height = hashlib.sha256(output.read_bytes()).hexdigest(), generated.width, generated.height
        source_type = f"{source_type}:{model.model}"
    version = ImageVersion(
        page_id=page.id, version_number=next_number, file_path=str(output), public_url=f"/media/{relative}",
        source_type=source_type, width=width, height=height, file_hash=digest,
        prompt=page.visual_description,
    )
    db.add(version)
    db.flush()
    page.current_version_id = version.id
    return version


def render_pages_parallel(db: Session, page_ids: list[str]) -> None:
    """在主 Graph 结束后并行生成内容包中的图片。

    SQLAlchemy Session 不能跨线程共享，因此每张图片都使用独立会话和事务。
    某张图片失败时，其他已成功图片仍会保留；再次请求内容包只会补生成
    尚无 current_version_id 的页面，避免重复消耗图片模型额度。
    """
    if not page_ids:
        return

    worker_sessions = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)

    def render_one(page_id: str) -> str:
        with worker_sessions() as worker_db:
            page = worker_db.get(ImagePage, page_id)
            if not page:
                raise RuntimeError(f"图片页面不存在：{page_id}")
            if page.current_version_id:
                return page_id
            render_page(worker_db, page)
            worker_db.commit()
            return page_id

    # 小红书内容包最多 5 张图。限制为 4 个并发，避免瞬间打满模型服务限流。
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=min(4, len(page_ids)), thread_name_prefix="image-generation") as executor:
        futures = {executor.submit(render_one, page_id): page_id for page_id in page_ids}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                errors.append(f"{futures[future]}: {exc}")
    if errors:
        raise HTTPException(502, "部分图片生成失败：" + "；".join(errors))


def create_package(db: Session, task_id: str) -> XiaohongshuPackage:
    # 图片生成耗时较长，同一个任务可能因为重复点击、重试或多个浏览器标签页
    # 同时进入这里。PostgreSQL 事务级 advisory lock 保证同一 task_id 同时只有
    # 一个创建者；等待者拿到锁后会读取并直接返回已生成的内容包。
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext(task_id))))
    existing = db.scalar(select(XiaohongshuPackage).where(XiaohongshuPackage.content_task_id == task_id))
    if existing:
        # 上一次并行任务可能只有部分页面失败；重试时只补齐失败页面。
        pending_page_ids = list(db.scalars(
            select(ImagePage.id).where(
                ImagePage.package_id == existing.id,
                ImagePage.current_version_id.is_(None),
            )
        ))
        render_pages_parallel(db, pending_page_ids)
        db.expire_all()
        return get_package(db, task_id)
    task = db.get(ContentTask, task_id)
    if not task:
        raise HTTPException(404, "内容任务不存在")
    if task.status != TaskStatus.completed:
        raise HTTPException(409, "文章审核完成后才能生成内容包")
    article = db.scalar(select(Article).where(Article.content_task_id == task_id))
    version = db.get(ArticleVersion, article.current_version_id) if article else None
    if not article or not version:
        raise HTTPException(409, "没有可用的已审核文章")
    body = _plain(version.content)
    package = XiaohongshuPackage(
        content_task_id=task_id, article_version_id=version.id, title=version.title[:20], body=body[:1000],
        tags="#AI编程 #LangGraph #AI应用开发 #编程学习", validation_message="内容包已通过基础长度校验",
    )
    db.add(package)
    db.flush()
    page_ids: list[str] = []
    for index, spec in enumerate(_visual_script(version), start=1):
        page = ImagePage(
            package_id=package.id, page_number=index, title=spec["title"], body=spec["body"],
            purpose=spec["purpose"], visual_description=f"简洁技术教育海报，{spec['purpose']}，统一品牌视觉",
        )
        db.add(page)
        db.flush()
        page_ids.append(page.id)
    # 先提交内容包和页面脚本。图片属于主 Graph 结束后的下游产物，随后使用
    # 独立会话并行生成，不把耗时的模型调用串进 LangGraph/checkpointer。
    db.commit()
    render_pages_parallel(db, page_ids)
    db.expire_all()
    return get_package(db, task_id)


async def save_upload(db: Session, page: ImagePage, upload: UploadFile) -> ImageVersion:
    if upload.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "只支持 PNG、JPEG 或 WebP 图片")
    data = await upload.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "图片不能超过 10MB")
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(422, "上传文件不是有效图片") from exc
    next_number = (db.scalar(select(func.max(ImageVersion.version_number)).where(ImageVersion.page_id == page.id)) or 0) + 1
    relative = f"{page.package_id}/{page.id}-v{next_number}.jpg"
    output = STORAGE_ROOT / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "JPEG", quality=92)
    version = ImageVersion(
        page_id=page.id, version_number=next_number, file_path=str(output), public_url=f"/media/{relative}",
        source_type="uploaded", width=image.width, height=image.height,
        file_hash=hashlib.sha256(output.read_bytes()).hexdigest(), prompt="人工上传替换",
    )
    db.add(version); db.flush(); page.current_version_id = version.id; db.commit(); db.refresh(version)
    return version


def export_package(package: XiaohongshuPackage) -> io.BytesIO:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = {"title": package.title, "body": package.body, "tags": package.tags, "images": []}
        for page in package.pages:
            current = next((v for v in page.versions if v.id == page.current_version_id), None)
            if current and Path(current.file_path).exists():
                name = f"images/{page.page_number:02d}.jpg" if current.file_path.endswith(".jpg") else f"images/{page.page_number:02d}.png"
                archive.write(current.file_path, name)
                manifest["images"].append(name)
        archive.writestr("content.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("copy.txt", f"{package.title}\n\n{package.body}\n\n{package.tags}")
    stream.seek(0)
    return stream
