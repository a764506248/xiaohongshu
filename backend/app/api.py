from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Article, ArticleVersion, ContentTask, ReviewRecord, TaskStatus, TopicCandidate
from app.schemas import (
    ArticleRead, ArticleVersionRead, ContentTaskCreate, ContentTaskRead, ContentTaskUpdate,
    GenerateRequest, HumanEdit, OperationResult, ReviewRead, ReviewRequest, TopicRead, TopicSelection,
)
from app.services import create_task, get_article_for_task, get_task_or_404, record_review, save_human_edit, update_task

router = APIRouter(prefix="/api/v1")


@router.post("/content-tasks", response_model=ContentTaskRead, status_code=201)
def create_content_task(data: ContentTaskCreate, db: Session = Depends(get_db)):
    return create_task(db, data)


@router.get("/content-tasks", response_model=list[ContentTaskRead])
def list_content_tasks(status: TaskStatus | None = None, db: Session = Depends(get_db)):
    query = select(ContentTask).order_by(ContentTask.created_at.desc())
    if status:
        query = query.where(ContentTask.status == status)
    return list(db.scalars(query))


@router.get("/content-tasks/{task_id}", response_model=ContentTaskRead)
def get_content_task(task_id: str, db: Session = Depends(get_db)):
    return get_task_or_404(db, task_id)


@router.patch("/content-tasks/{task_id}", response_model=ContentTaskRead)
def patch_content_task(task_id: str, data: ContentTaskUpdate, db: Session = Depends(get_db)):
    return update_task(db, get_task_or_404(db, task_id), data)


@router.post("/content-tasks/{task_id}/generate-topics", response_model=OperationResult)
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


@router.get("/content-tasks/{task_id}/topics", response_model=list[TopicRead])
def list_topics(task_id: str, db: Session = Depends(get_db)):
    get_task_or_404(db, task_id)
    return list(db.scalars(select(TopicCandidate).where(TopicCandidate.content_task_id == task_id).order_by(TopicCandidate.score.desc())))


@router.post("/content-tasks/{task_id}/select-topic", response_model=OperationResult)
def select_topic(task_id: str, data: TopicSelection, request: Request, db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    if task.status != TaskStatus.waiting_topic_selection:
        raise HTTPException(409, "任务当前不在选题阶段")
    request.app.state.workflow.resume(task.id, {"topic_id": data.topic_id})
    return OperationResult(status="waiting_article_review", task_id=task.id)


@router.get("/content-tasks/{task_id}/article", response_model=ArticleRead)
def get_article(task_id: str, db: Session = Depends(get_db)):
    get_task_or_404(db, task_id)
    return get_article_for_task(db, task_id)


@router.get("/articles/{article_id}/versions", response_model=list[ArticleVersionRead])
def list_versions(article_id: str, db: Session = Depends(get_db)):
    if not db.get(Article, article_id):
        raise HTTPException(404, "文章不存在")
    return list(db.scalars(select(ArticleVersion).where(ArticleVersion.article_id == article_id).order_by(ArticleVersion.version_number)))


@router.post("/articles/{article_id}/versions", response_model=ArticleVersionRead, status_code=201)
def create_human_version(article_id: str, data: HumanEdit, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文章不存在")
    article = get_article_for_task(db, article.content_task_id)
    return save_human_edit(db, article, data)


@router.post("/content-tasks/{task_id}/review", response_model=ReviewRead)
def review_article(task_id: str, data: ReviewRequest, request: Request, db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    record, created = record_review(db, task, data)
    if created:
        request.app.state.workflow.resume(task.id, data.model_dump())
    return record


@router.get("/content-tasks/{task_id}/reviews", response_model=list[ReviewRead])
def list_reviews(task_id: str, db: Session = Depends(get_db)):
    get_task_or_404(db, task_id)
    return list(db.scalars(select(ReviewRecord).where(ReviewRecord.content_task_id == task_id).order_by(ReviewRecord.created_at)))
