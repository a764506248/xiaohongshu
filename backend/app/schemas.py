from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import TaskStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ContentTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    requirement: str = ""
    target_audience: str = "AI 编程学习者"


class ContentTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    requirement: str | None = None
    target_audience: str | None = None


class ContentTaskRead(ORMModel):
    id: str
    title: str
    requirement: str
    target_audience: str
    status: TaskStatus
    current_stage: str
    selected_topic_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TopicRead(ORMModel):
    id: str
    content_task_id: str
    title: str
    summary: str
    target_reader: str
    reason: str
    score: float
    status: str


class TopicSelection(BaseModel):
    topic_id: str


class GenerateRequest(BaseModel):
    instruction: str = ""


class ArticleVersionRead(ORMModel):
    id: str
    article_id: str
    version_number: int
    title: str
    outline: str
    content: str
    generation_instruction: str
    source_type: str
    created_at: datetime


class ArticleRead(ORMModel):
    id: str
    content_task_id: str
    selected_topic_id: str
    status: str
    current_version_id: str | None
    versions: list[ArticleVersionRead]


class HumanEdit(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    content: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    decision: Literal["approve", "reject", "edit_and_approve", "regenerate"]
    comment: str = ""
    reviewer_id: str = "operator"
    edited_title: str | None = None
    edited_content: str | None = None


class ReviewRead(ORMModel):
    id: str
    request_id: str
    content_task_id: str
    article_version_id: str
    decision: str
    comment: str
    reviewer_id: str
    created_at: datetime


class OperationResult(BaseModel):
    status: str
    task_id: str
    detail: str = ""

