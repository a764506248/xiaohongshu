from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.media import create_package, export_package, get_package, render_page, save_upload
from app.models import Article, ArticleVersion, ContentTask, ImagePage, ReviewRecord, TaskStatus, TopicCandidate, XiaohongshuPackage
from app.schemas import (
    ArticleRead, ArticleVersionRead, ContentTaskCreate, ContentTaskRead, ContentTaskUpdate,
    GenerateRequest, HumanEdit, ImagePageRead, ImagePageUpdate, ImageVersionRead, OperationResult,
    PageOrderUpdate, ReviewRead, ReviewRequest, TopicRead, TopicSelection, XiaohongshuPackageRead,
    XiaohongshuPackageUpdate,
)
from app.services import create_task, get_article_for_task, get_task_or_404, record_review, save_human_edit, update_task

router = APIRouter(prefix="/api/v1")


@router.post("/content-tasks", response_model=ContentTaskRead, status_code=201, tags=["内容任务"], summary="创建内容任务", description="创建一次新的内容生产任务。创建后状态为 draft，下一步调用生成候选选题接口。")
def create_content_task(data: ContentTaskCreate, db: Session = Depends(get_db)):
    return create_task(db, data)


@router.get("/content-tasks", response_model=list[ContentTaskRead], tags=["内容任务"], summary="查询内容任务列表", description="按创建时间倒序返回任务。可使用 status 参数筛选任务状态。")
def list_content_tasks(status: TaskStatus | None = None, db: Session = Depends(get_db)):
    query = select(ContentTask).order_by(ContentTask.created_at.desc())
    if status:
        query = query.where(ContentTask.status == status)
    return list(db.scalars(query))


@router.get("/content-tasks/{task_id}", response_model=ContentTaskRead, tags=["内容任务"], summary="查询单个内容任务", description="返回任务当前业务状态、所处阶段、已选选题和最新错误。")
def get_content_task(task_id: str, db: Session = Depends(get_db)):
    return get_task_or_404(db, task_id)


@router.patch("/content-tasks/{task_id}", response_model=ContentTaskRead, tags=["内容任务"], summary="修改任务要求", description="仅 draft 或 failed 状态允许修改主题、目标受众和补充要求。")
def patch_content_task(task_id: str, data: ContentTaskUpdate, db: Session = Depends(get_db)):
    return update_task(db, get_task_or_404(db, task_id), data)


@router.post("/content-tasks/{task_id}/generate-topics", response_model=OperationResult, tags=["候选选题"], summary="生成候选选题", description="启动新的 LangGraph 线程，请求 SenseNova 生成候选选题，然后在人工选择节点暂停。失败任务也可通过此接口重新开始。")
def generate_topics(task_id: str, data: GenerateRequest, request: Request, db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    if task.status not in {TaskStatus.draft, TaskStatus.failed, TaskStatus.waiting_topic_selection}:
        raise HTTPException(409, "当前阶段不能生成选题")
    try:
        request.app.state.workflow.start(task.id, data.instruction)
    except Exception as exc:
        task.status = TaskStatus.failed
        task.error_message = str(exc)
        db.commit()
        raise HTTPException(502, f"生成选题失败：{exc}") from exc
    return OperationResult(status="waiting_topic_selection", task_id=task.id)


@router.get("/content-tasks/{task_id}/topics", response_model=list[TopicRead], tags=["候选选题"], summary="查询候选选题", description="按 AI 评分从高到低返回当前任务的候选选题。")
def list_topics(task_id: str, db: Session = Depends(get_db)):
    get_task_or_404(db, task_id)
    return list(db.scalars(select(TopicCandidate).where(TopicCandidate.content_task_id == task_id).order_by(TopicCandidate.score.desc())))


@router.post("/content-tasks/{task_id}/select-topic", response_model=OperationResult, tags=["候选选题"], summary="选择选题并生成文章", description="仅 waiting_topic_selection 状态可调用。提交 topic_id 后恢复 LangGraph，并同步生成 Markdown 文章。")
def select_topic(task_id: str, data: TopicSelection, request: Request, db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    if task.status != TaskStatus.waiting_topic_selection:
        raise HTTPException(409, "任务当前不在选题阶段")
    try:
        request.app.state.workflow.resume(task.id, {"topic_id": data.topic_id})
    except Exception as exc:
        db.expire_all()
        task = get_task_or_404(db, task_id)
        task.status = TaskStatus.failed
        task.current_stage = "failed"
        task.error_message = str(exc)
        db.commit()
        raise HTTPException(502, f"生成文案失败：{exc}") from exc
    return OperationResult(status="waiting_article_review", task_id=task.id)


@router.get("/content-tasks/{task_id}/article", response_model=ArticleRead, tags=["文章与版本"], summary="查询任务文章", description="返回文章主体和全部历史版本。current_version_id 指向当前审核或发布使用的版本。")
def get_article(task_id: str, db: Session = Depends(get_db)):
    get_task_or_404(db, task_id)
    return get_article_for_task(db, task_id)


@router.get("/articles/{article_id}/versions", response_model=list[ArticleVersionRead], tags=["文章与版本"], summary="查询文章版本", description="按版本号升序返回 AI 初稿、AI 修订稿和人工编辑稿。")
def list_versions(article_id: str, db: Session = Depends(get_db)):
    if not db.get(Article, article_id):
        raise HTTPException(404, "文章不存在")
    return list(db.scalars(select(ArticleVersion).where(ArticleVersion.article_id == article_id).order_by(ArticleVersion.version_number)))


@router.post("/articles/{article_id}/versions", response_model=ArticleVersionRead, status_code=201, tags=["文章与版本"], summary="保存人工编辑版本", description="保存标题和正文为新的 human_edited 版本，不覆盖旧版本。")
def create_human_version(article_id: str, data: HumanEdit, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文章不存在")
    article = get_article_for_task(db, article.content_task_id)
    return save_human_edit(db, article, data)


@router.post("/content-tasks/{task_id}/review", response_model=ReviewRead, tags=["人工审核"], summary="提交文章审核决定", description="仅 waiting_article_review 状态可调用。支持 approve、reject、edit_and_approve 和 regenerate；相同 request_id 只处理一次。")
def review_article(task_id: str, data: ReviewRequest, request: Request, db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    record, created = record_review(db, task, data)
    if created:
        request.app.state.workflow.resume(task.id, data.model_dump())
    return record


@router.get("/content-tasks/{task_id}/reviews", response_model=list[ReviewRead], tags=["人工审核"], summary="查询审核历史", description="返回任务全部审核决定、意见、审核人和对应文章版本。")
def list_reviews(task_id: str, db: Session = Depends(get_db)):
    get_task_or_404(db, task_id)
    return list(db.scalars(select(ReviewRecord).where(ReviewRecord.content_task_id == task_id).order_by(ReviewRecord.created_at)))


@router.post("/content-tasks/{task_id}/xiaohongshu-package", response_model=XiaohongshuPackageRead, tags=["小红书内容包"], summary="生成小红书内容包", description="仅审核完成的任务可调用。将当前文章版本转换为发布文案和 3～5 个图片页面；重复调用返回已有内容包。")
def generate_xiaohongshu_package(task_id: str, db: Session = Depends(get_db)):
    return create_package(db, task_id)


@router.get("/content-tasks/{task_id}/xiaohongshu-package", response_model=XiaohongshuPackageRead, tags=["小红书内容包"], summary="查询小红书内容包", description="返回标题、正文、标签、图片页面及每页全部图片版本。")
def read_xiaohongshu_package(task_id: str, db: Session = Depends(get_db)):
    return get_package(db, task_id)


@router.patch("/content-tasks/{task_id}/xiaohongshu-package", response_model=XiaohongshuPackageRead, tags=["小红书内容包"], summary="修改发布文案", description="修改小红书标题、正文和话题标签，不影响文章母稿。")
def update_xiaohongshu_package(task_id: str, data: XiaohongshuPackageUpdate, db: Session = Depends(get_db)):
    package = get_package(db, task_id)
    package.title = data.title
    package.body = data.body
    package.tags = data.tags
    package.validation_message = "内容包已保存"
    db.commit()
    return get_package(db, task_id)


@router.patch("/image-pages/{page_id}", response_model=ImagePageRead, tags=["图片页面"], summary="修改页面文字和模板", description="保存页面标题、短正文和模板，并立即渲染一个新的图片版本。模板可选 editorial、dark、warm。")
def update_image_page(page_id: str, data: ImagePageUpdate, db: Session = Depends(get_db)):
    page = db.get(ImagePage, page_id)
    if not page:
        raise HTTPException(404, "图片页面不存在")
    page.title = data.title
    page.body = data.body
    page.template = data.template
    render_page(db, page, "text_edited")
    db.commit()
    package = db.get(XiaohongshuPackage, page.package_id)
    return next(item for item in get_package(db, package.content_task_id).pages if item.id == page_id)


@router.post("/image-pages/{page_id}/regenerate", response_model=ImageVersionRead, tags=["图片页面"], summary="重新生成单张图片", description="使用当前文字和模板重新渲染图片，产生新的 regenerated 版本。")
def regenerate_image_page(page_id: str, db: Session = Depends(get_db)):
    page = db.get(ImagePage, page_id)
    if not page:
        raise HTTPException(404, "图片页面不存在")
    version = render_page(db, page, "regenerated")
    db.commit(); db.refresh(version)
    return version


@router.post("/image-pages/{page_id}/upload", response_model=ImageVersionRead, tags=["图片页面"], summary="上传图片替换", description="上传 PNG、JPEG 或 WebP 作为当前页面的新版本，最大 10MB。")
async def upload_image_page(
    page_id: str,
    file: UploadFile = File(..., description="用于替换当前页面的 PNG、JPEG 或 WebP 图片，最大 10MB"),
    db: Session = Depends(get_db),
):
    page = db.get(ImagePage, page_id)
    if not page:
        raise HTTPException(404, "图片页面不存在")
    return await save_upload(db, page, file)


@router.put("/content-tasks/{task_id}/xiaohongshu-package/page-order", response_model=XiaohongshuPackageRead, tags=["小红书内容包"], summary="调整图片页面顺序", description="page_ids 必须包含该内容包全部页面 ID，数组顺序即新的页面顺序。")
def reorder_image_pages(task_id: str, data: PageOrderUpdate, db: Session = Depends(get_db)):
    package = get_package(db, task_id)
    existing = {page.id: page for page in package.pages}
    if set(data.page_ids) != set(existing):
        raise HTTPException(422, "页面列表与内容包不匹配")
    for index, page_id in enumerate(data.page_ids, start=1):
        existing[page_id].page_number = -index
    db.flush()
    for index, page_id in enumerate(data.page_ids, start=1):
        existing[page_id].page_number = index
    db.commit()
    db.expire_all()
    return get_package(db, task_id)


@router.get("/content-tasks/{task_id}/xiaohongshu-package/export", tags=["小红书内容包"], summary="导出内容包 ZIP", description="下载当前图片版本、content.json 和可直接复制的 copy.txt。", response_class=StreamingResponse)
def download_xiaohongshu_package(task_id: str, db: Session = Depends(get_db)):
    package = get_package(db, task_id)
    return StreamingResponse(
        export_package(package), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="xiaohongshu-{task_id}.zip"'},
    )
