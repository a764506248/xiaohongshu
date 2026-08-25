from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ChannelAccount, ChannelVariant, ModelUsageEvent, PostMetric, PreferenceSignal, PublishAttempt, PublishJob
from app.operations import analytics_summary, create_channel_variants, create_publish_job, duplicate_topics, execute_job, process_due_jobs, save_metric, update_variant
from app.schemas import (
    AnalyticsSummary, ChannelAccountCreate, ChannelAccountRead, ChannelVariantRead,
    ChannelVariantUpdate, ManualPublishComplete, MetricCreate, MetricRead, ModelUsageRead,
    PreferenceSignalRead, PublishDecision, PublishJobCreate, PublishJobRead, TopicDuplicateRead,
)

router = APIRouter(prefix="/api/v1")


@router.post("/channel-accounts", response_model=ChannelAccountRead, status_code=201, tags=["渠道账号"], summary="创建渠道账号")
def create_account(data: ChannelAccountCreate, db: Session = Depends(get_db)):
    account = ChannelAccount(**data.model_dump())
    db.add(account); db.commit(); db.refresh(account)
    return account


@router.get("/channel-accounts", response_model=list[ChannelAccountRead], tags=["渠道账号"], summary="查询渠道账号")
def list_accounts(channel: str | None = Query(default=None, description="按平台过滤"), db: Session = Depends(get_db)):
    query = select(ChannelAccount).order_by(ChannelAccount.created_at.desc())
    if channel:
        query = query.where(ChannelAccount.channel == channel)
    return list(db.scalars(query))


@router.post("/content-tasks/{task_id}/channel-variants", response_model=list[ChannelVariantRead], tags=["多平台内容"], summary="生成平台内容版本")
def generate_variants(task_id: str, db: Session = Depends(get_db)):
    return create_channel_variants(db, task_id)


@router.get("/content-tasks/{task_id}/channel-variants", response_model=list[ChannelVariantRead], tags=["多平台内容"], summary="查询平台内容版本")
def list_variants(task_id: str, db: Session = Depends(get_db)):
    return list(db.scalars(select(ChannelVariant).where(ChannelVariant.content_task_id == task_id).order_by(ChannelVariant.channel)))


@router.patch("/channel-variants/{variant_id}", response_model=ChannelVariantRead, tags=["多平台内容"], summary="编辑平台内容版本")
def edit_variant(variant_id: str, data: ChannelVariantUpdate, db: Session = Depends(get_db)):
    item = db.get(ChannelVariant, variant_id)
    if not item:
        raise HTTPException(404, "平台内容版本不存在")
    return update_variant(db, item, data)


@router.post("/publish-jobs", response_model=PublishJobRead, status_code=201, tags=["发布任务"], summary="创建发布任务")
def add_publish_job(data: PublishJobCreate, db: Session = Depends(get_db)):
    return create_publish_job(db, data)


@router.get("/publish-jobs", response_model=list[PublishJobRead], tags=["发布任务"], summary="查询发布任务与排期")
def list_publish_jobs(status: str | None = Query(default=None, description="按发布状态过滤"), db: Session = Depends(get_db)):
    query = select(PublishJob).order_by(PublishJob.scheduled_at.desc(), PublishJob.created_at.desc())
    if status:
        query = query.where(PublishJob.status == status)
    return list(db.scalars(query))


@router.post("/publish-jobs/{job_id}/decision", response_model=PublishJobRead, tags=["发布任务"], summary="审批发布任务")
def decide_publish_job(job_id: str, data: PublishDecision, db: Session = Depends(get_db)):
    job = db.get(PublishJob, job_id)
    if not job:
        raise HTTPException(404, "发布任务不存在")
    job.approval_status = "approved" if data.decision == "approve" else "rejected"
    job.status = "approved" if data.decision == "approve" else "rejected"
    job.error_message = data.comment or None
    db.commit(); db.refresh(job)
    return execute_job(db, job) if data.decision == "approve" else job


@router.post("/publish-jobs/{job_id}/execute", response_model=PublishJobRead, tags=["发布任务"], summary="立即执行发布任务")
def run_publish_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(PublishJob, job_id)
    if not job:
        raise HTTPException(404, "发布任务不存在")
    return execute_job(db, job)


@router.post("/publish-jobs/{job_id}/retry", response_model=PublishJobRead, tags=["发布任务"], summary="重试失败任务")
def retry_publish_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(PublishJob, job_id)
    if not job:
        raise HTTPException(404, "发布任务不存在")
    if job.status != "failed":
        raise HTTPException(409, "只有失败任务可以重试")
    if job.retry_count >= job.max_retries:
        raise HTTPException(409, "已经达到最大重试次数")
    job.status = "approved"; db.commit()
    return execute_job(db, job)


@router.post("/publish-jobs/{job_id}/complete-manual", response_model=PublishJobRead, tags=["发布任务"], summary="确认人工发布完成")
def complete_manual(job_id: str, data: ManualPublishComplete, db: Session = Depends(get_db)):
    job = db.get(PublishJob, job_id)
    if not job:
        raise HTTPException(404, "发布任务不存在")
    if job.status != "awaiting_manual_publish":
        raise HTTPException(409, "任务当前不在等待人工发布状态")
    job.status = "published"; job.published_at = datetime.utcnow(); job.external_post_id = data.external_post_id
    variant = db.get(ChannelVariant, job.channel_variant_id); variant.status = "published"
    db.add(PublishAttempt(publish_job_id=job.id, attempt_number=job.retry_count + 1, status="manual_success", response_excerpt=data.external_post_id))
    db.commit(); db.refresh(job)
    return job


@router.post("/publish-jobs/process-due", tags=["发布任务"], summary="处理到期的发布任务")
def process_jobs(db: Session = Depends(get_db)):
    return {"processed": process_due_jobs(db)}


@router.post("/publish-jobs/{job_id}/metrics", response_model=MetricRead, status_code=201, tags=["运营数据"], summary="录入发布效果指标")
def add_metric(job_id: str, data: MetricCreate, db: Session = Depends(get_db)):
    job = db.get(PublishJob, job_id)
    if not job:
        raise HTTPException(404, "发布任务不存在")
    return save_metric(db, job, data)


@router.get("/publish-jobs/{job_id}/metrics", response_model=list[MetricRead], tags=["运营数据"], summary="查询发布效果指标")
def list_metrics(job_id: str, db: Session = Depends(get_db)):
    return list(db.scalars(select(PostMetric).where(PostMetric.publish_job_id == job_id).order_by(PostMetric.collected_at.desc())))


@router.get("/analytics/summary", response_model=AnalyticsSummary, tags=["运营数据"], summary="查询运营数据总览")
def get_analytics_summary(db: Session = Depends(get_db)):
    return analytics_summary(db)


@router.get("/analytics/preferences", response_model=list[PreferenceSignalRead], tags=["运营数据"], summary="查询内容偏好信号")
def get_preferences(db: Session = Depends(get_db)):
    return list(db.scalars(select(PreferenceSignal).order_by(PreferenceSignal.weight.desc())))


@router.get("/analytics/topic-duplicates", response_model=list[TopicDuplicateRead], tags=["运营数据"], summary="检查标题重复度")
def check_duplicates(title: str = Query(min_length=1, description="准备使用的新标题"), db: Session = Depends(get_db)):
    return duplicate_topics(db, title)


@router.get("/analytics/model-usage", response_model=list[ModelUsageRead], tags=["运营数据"], summary="查询模型调用和成本记录")
def get_model_usage(db: Session = Depends(get_db)):
    return list(db.scalars(select(ModelUsageEvent).order_by(ModelUsageEvent.created_at.desc()).limit(200)))
