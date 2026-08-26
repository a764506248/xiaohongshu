from typing import TypedDict


class ContentState(TypedDict, total=False):
    task_id: str
    instruction: str
    llm_topic_count: int
    rag_topic_count: int
    topic_id: str
    article_id: str
    review: dict
