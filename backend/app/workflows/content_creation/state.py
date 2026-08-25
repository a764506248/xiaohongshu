from typing import TypedDict


class ContentState(TypedDict, total=False):
    task_id: str
    instruction: str
    topic_id: str
    article_id: str
    review: dict

