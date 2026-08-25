from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Article, ArticleVersion, ContentTask, ReviewRecord, TaskStatus, TopicCandidate
from app.schemas import ContentTaskCreate, ContentTaskUpdate, HumanEdit, ReviewRequest


def get_task_or_404(db: Session, task_id: str) -> ContentTask:
    task = db.get(ContentTask, task_id)
    if not task:
        raise HTTPException(404, "内容任务不存在")
    return task


def create_task(db: Session, data: ContentTaskCreate) -> ContentTask:
    task = ContentTask(**data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: ContentTask, data: ContentTaskUpdate) -> ContentTask:
    if task.status not in {TaskStatus.draft, TaskStatus.failed}:
        raise HTTPException(409, "当前阶段不允许修改任务要求")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def get_article_for_task(db: Session, task_id: str) -> Article:
    article = db.scalar(
        select(Article).options(selectinload(Article.versions)).where(Article.content_task_id == task_id)
    )
    if not article:
        raise HTTPException(404, "文章尚未生成")
    return article


def save_human_edit(db: Session, article: Article, data: HumanEdit) -> ArticleVersion:
    number = max((item.version_number for item in article.versions), default=0) + 1
    version = ArticleVersion(
        article_id=article.id,
        version_number=number,
        title=data.title,
        content=data.content,
        outline="",
        source_type="human_edited",
    )
    db.add(version)
    db.flush()
    article.current_version_id = version.id
    db.commit()
    db.refresh(version)
    return version


def record_review(db: Session, task: ContentTask, data: ReviewRequest) -> tuple[ReviewRecord, bool]:
    existing = db.scalar(select(ReviewRecord).where(ReviewRecord.request_id == data.request_id))
    if existing:
        return existing, False
    article = get_article_for_task(db, task.id)
    if task.status != TaskStatus.waiting_article_review or not article.current_version_id:
        raise HTTPException(409, "任务当前不在文案审核阶段")
    if data.decision == "edit_and_approve":
        if not data.edited_title or not data.edited_content:
            raise HTTPException(422, "修改后通过需要提交标题和正文")
        version = save_human_edit(db, article, HumanEdit(title=data.edited_title, content=data.edited_content))
        article = get_article_for_task(db, task.id)
    record = ReviewRecord(
        request_id=data.request_id,
        content_task_id=task.id,
        article_version_id=article.current_version_id,
        decision=data.decision,
        comment=data.comment,
        reviewer_id=data.reviewer_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, True

