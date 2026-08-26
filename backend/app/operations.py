import html
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.media import get_package
from app.models import (
    Article, ArticleVersion, ChannelAccount, ChannelVariant, ContentTask, ModelUsageEvent,
    PostMetric, PreferenceSignal, PublishAttempt, PublishJob, TaskStatus,
)
from app.schemas import ChannelVariantUpdate, MetricCreate, PublishJobCreate


def markdown_to_html(markdown: str) -> str:
    lines = []
    for raw in markdown.splitlines():
        value = html.escape(raw.strip())
        if not value:
            continue
        if value.startswith("### "):
            lines.append(f"<h3>{value[4:]}</h3>")
        elif value.startswith("## "):
            lines.append(f"<h2>{value[3:]}</h2>")
        elif value.startswith("# "):
            lines.append(f"<h1>{value[2:]}</h1>")
        elif re.match(r"^\d+\. ", value):
            lines.append(f"<p><strong>{value}</strong></p>")
        else:
            lines.append(f"<p>{value}</p>")
    return "\n".join(lines)


def create_channel_variants(db: Session, task_id: str) -> list[ChannelVariant]:
    task = db.get(ContentTask, task_id)
    if not task:
        raise HTTPException(404, "内容任务不存在")
    if task.status != TaskStatus.completed:
        raise HTTPException(409, "文章审核完成后才能生成平台版本")
    article = db.scalar(select(Article).where(Article.content_task_id == task_id))
    version = db.get(ArticleVersion, article.current_version_id) if article else None
    if not version:
        raise HTTPException(409, "没有可用的已审核文章")
    package = None
    try:
        package = get_package(db, task_id)
    except HTTPException:
        pass
    variants = []
    for channel in ("xiaohongshu", "wechat"):
        item = db.scalar(select(ChannelVariant).where(ChannelVariant.content_task_id == task_id, ChannelVariant.channel == channel))
        if not item:
            if channel == "xiaohongshu" and package:
                title, body, tags = package.title, package.body, package.tags
                cover = next((v.public_url for p in package.pages for v in p.versions if v.id == p.current_version_id), "")
            else:
                title, body, tags, cover = version.title, version.content, "", ""
            item = ChannelVariant(
                content_task_id=task_id, article_version_id=version.id, channel=channel,
                title=title, summary=re.sub(r"[#>*_`]", "", body)[:120], body=body,
                html_content=markdown_to_html(body), cover_url=cover, tags=tags, status="ready",
            )
            db.add(item)
        variants.append(item)
    db.commit()
    return list(db.scalars(select(ChannelVariant).where(ChannelVariant.content_task_id == task_id).order_by(ChannelVariant.channel)))


def update_variant(db: Session, item: ChannelVariant, data: ChannelVariantUpdate) -> ChannelVariant:
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    item.html_content = markdown_to_html(item.body)
    item.status = "ready"
    db.commit(); db.refresh(item)
    return item


class ChannelAdapter:
    def publish(self, account: ChannelAccount, variant: ChannelVariant, key: str) -> str:
        raise NotImplementedError


class MockChannelAdapter(ChannelAdapter):
    def publish(self, account: ChannelAccount, variant: ChannelVariant, key: str) -> str:
        return f"mock-{account.channel}-{uuid.uuid5(uuid.NAMESPACE_URL, key)}"


def create_publish_job(db: Session, data: PublishJobCreate) -> PublishJob:
    existing = db.scalar(select(PublishJob).where(PublishJob.idempotency_key == data.idempotency_key))
    if existing:
        return existing
    variant = db.get(ChannelVariant, data.channel_variant_id)
    account = db.get(ChannelAccount, data.channel_account_id)
    if not variant or not account:
        raise HTTPException(404, "平台版本或平台账号不存在")
    if variant.channel != account.channel:
        raise HTTPException(422, "平台版本与账号渠道不匹配")
    job = PublishJob(**data.model_dump(), status="pending_approval", approval_status="pending")
    db.add(job); db.commit(); db.refresh(job)
    return job


def execute_job(db: Session, job: PublishJob) -> PublishJob:
    if job.status == "published":
        return job
    if job.approval_status != "approved":
        raise HTTPException(409, "发布任务尚未审批通过")
    if job.scheduled_at and job.scheduled_at > datetime.utcnow():
        job.status = "scheduled"; db.commit(); return job
    account = db.get(ChannelAccount, job.channel_account_id)
    variant = db.get(ChannelVariant, job.channel_variant_id)
    if account.mode == "manual":
        job.status = "awaiting_manual_publish"; db.commit(); return job
    job.status = "publishing"; db.commit()
    try:
        external_id = MockChannelAdapter().publish(account, variant, job.idempotency_key)
        job.external_post_id = external_id; job.status = "published"; job.published_at = datetime.utcnow()
        variant.status = "published"
        attempt = PublishAttempt(publish_job_id=job.id, attempt_number=job.retry_count + 1, status="success", response_excerpt=external_id)
    except Exception as exc:
        job.retry_count += 1; job.error_message = str(exc); job.status = "failed"
        attempt = PublishAttempt(publish_job_id=job.id, attempt_number=job.retry_count, status="failed", response_excerpt=str(exc)[:500])
    db.add(attempt); db.commit(); db.refresh(job)
    return job


def process_due_jobs(db: Session) -> int:
    now = datetime.utcnow()
    jobs = list(db.scalars(select(PublishJob).where(
        PublishJob.approval_status == "approved",
        PublishJob.status.in_(["scheduled", "approved", "failed"]),
        (PublishJob.scheduled_at.is_(None)) | (PublishJob.scheduled_at <= now),
        PublishJob.retry_count < PublishJob.max_retries,
    )))
    for job in jobs:
        execute_job(db, job)
    return len(jobs)


def score_metric(data: MetricCreate) -> float:
    views = max(data.views, 1)
    weighted = data.likes + data.comments * 2 + data.favorites * 3 + data.shares * 4 + max(data.follower_gain, 0) * 5
    return round(min(100.0, weighted / views * 500), 2)


def save_metric(db: Session, job: PublishJob, data: MetricCreate) -> PostMetric:
    if job.status != "published":
        raise HTTPException(409, "只有已发布任务可以录入指标")
    metric = PostMetric(publish_job_id=job.id, performance_score=score_metric(data), **data.model_dump())
    db.add(metric)
    variant = db.get(ChannelVariant, job.channel_variant_id)
    signals = [("channel", variant.channel)] + [("tag", tag) for tag in variant.tags.split() if tag.startswith("#")]
    for signal_type, value in signals:
        signal = db.scalar(select(PreferenceSignal).where(PreferenceSignal.signal_type == signal_type, PreferenceSignal.signal_value == value))
        if not signal:
            signal = PreferenceSignal(signal_type=signal_type, signal_value=value)
            db.add(signal)
        total = signal.weight * signal.sample_count + metric.performance_score
        signal.sample_count += 1; signal.weight = round(total / signal.sample_count, 2)
    db.commit(); db.refresh(metric)
    return metric


def analytics_summary(db: Session) -> dict:
    published = db.scalar(select(func.count()).select_from(PublishJob).where(PublishJob.status == "published")) or 0
    totals = db.execute(select(
        func.coalesce(func.sum(PostMetric.views), 0),
        func.coalesce(func.sum(PostMetric.likes + PostMetric.favorites + PostMetric.comments + PostMetric.shares), 0),
        func.coalesce(func.avg(PostMetric.performance_score), 0),
    )).one()
    calls, cost, input_tokens, output_tokens, latency = db.execute(select(
        func.count(ModelUsageEvent.id), func.coalesce(func.sum(ModelUsageEvent.estimated_cost), 0),
        func.coalesce(func.sum(ModelUsageEvent.input_tokens), 0), func.coalesce(func.sum(ModelUsageEvent.output_tokens), 0),
        func.coalesce(func.sum(ModelUsageEvent.latency_ms), 0),
    )).one()
    signals = list(db.scalars(select(PreferenceSignal).order_by(PreferenceSignal.weight.desc()).limit(10)))
    return {"published_posts": published, "total_views": totals[0], "total_interactions": totals[1], "average_score": round(float(totals[2]), 2), "model_calls": calls, "total_input_tokens": input_tokens, "total_output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens, "total_latency_ms": latency, "estimated_model_cost": float(cost), "top_signals": signals}


def token_usage_report(db: Session, start_at: datetime, end_at: datetime, granularity: str) -> dict:
    rows = list(db.scalars(select(ModelUsageEvent).where(
        ModelUsageEvent.created_at >= start_at,
        ModelUsageEvent.created_at <= end_at,
    ).order_by(ModelUsageEvent.created_at)))
    formats = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}
    buckets: dict[str, dict] = {}
    for row in rows:
        period = row.created_at.strftime(formats[granularity])
        point = buckets.setdefault(period, {"period": period, "calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "latency_ms": 0})
        point["calls"] += 1
        point["input_tokens"] += row.input_tokens
        point["output_tokens"] += row.output_tokens
        point["total_tokens"] += row.input_tokens + row.output_tokens
        point["latency_ms"] += row.latency_ms
    points = list(buckets.values())
    return {"granularity": granularity, "start_at": start_at, "end_at": end_at, "calls": sum(p["calls"] for p in points), "input_tokens": sum(p["input_tokens"] for p in points), "output_tokens": sum(p["output_tokens"] for p in points), "total_tokens": sum(p["total_tokens"] for p in points), "points": points}


def duplicate_topics(db: Session, title: str, limit: int = 5) -> list[dict]:
    rows = list(db.scalars(select(ChannelVariant).order_by(ChannelVariant.created_at.desc()).limit(100)))
    matches = [{"title": row.title, "channel": row.channel, "similarity": round(SequenceMatcher(None, title.lower(), row.title.lower()).ratio(), 3)} for row in rows]
    return sorted(matches, key=lambda x: x["similarity"], reverse=True)[:limit]
