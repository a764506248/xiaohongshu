import logging
import uuid

# END、START 是 LangGraph 内置的起点和终点；StateGraph 用于声明流程图。
from langgraph.graph import END, START, StateGraph
# Command(resume=...) 用于恢复暂停的流程；interrupt() 用于主动暂停流程。
from langgraph.types import Command, interrupt
# func 用来执行 max 等数据库函数；select 用来构造 SQLAlchemy 查询。
from sqlalchemy import case, func, select
# Session 是数据库会话类型；sessionmaker 是创建会话的工厂。
from sqlalchemy.orm import Session, sessionmaker

# LLMProvider 隔离具体模型服务商；TopicOutput 是传给文章生成器的选题结构。
from app.ai.provider import FallbackLLMProvider, LLMProvider, TopicOutput, provider_from_model_configuration
from app.core.config import get_settings
# 数据库保存完整业务数据；LangGraph state 只保存这些数据的 ID 和路由信息。
from app.models import Article, ArticleVersion, ContentTask, ModelConfiguration, ModelUsageEvent, ReviewRecord, TaskStatus, TopicCandidate
# ContentState 定义整个图运行过程中可以携带的字段。
from app.workflows.content_creation.state import ContentState
from app.workflows.content_creation.topic_subgraph import TopicGenerationSubgraph

# 使用模块级 logger，日志格式和输出位置由 FastAPI/Uvicorn 统一控制。
logger = logging.getLogger(__name__)


class ContentWorkflow:
    """内容生产 LangGraph 工作流。

    完整路线：
    START → 生成候选选题 → 等待人工选题 → 生成文章 → 等待人工审核
      ├─ 通过/修改后通过 → 完成 → END
      └─ 退回/重新生成 → 再次生成文章 → 再次等待审核

    注意：图片、多平台发布和数据运营不在这张图中。它们在文章审核完成后，
    由普通业务服务继续处理，避免让核心内容工作流变得过于复杂。
    """

    def __init__(self, session_factory: sessionmaker[Session], llm: LLMProvider, checkpointer):
        # 保存数据库会话工厂。每个节点运行时都会创建独立数据库会话。
        self.session_factory = session_factory
        # 保存模型适配器。节点只调用统一接口，不关心底层是 SenseNova、OpenRouter 还是测试 Mock。
        self.llm = llm

        # 创建一张以 ContentState 为共享状态结构的有向图。
        builder = StateGraph(ContentState)

        # 选题生成本身是一张子图：LLM 生成、RAG 召回、合并排序、持久化都可独立迭代。
        self.topic_generation = TopicGenerationSubgraph(session_factory, self._llm_for_task)
        # 主图仍使用 generate_topics 这个稳定节点名，后续主流程无需感知子图内部变化。
        builder.add_node("generate_topics", self.topic_generation.graph)
        builder.add_node("select_topic", self.select_topic)
        builder.add_node("generate_article", self.generate_article)
        builder.add_node("review_article", self.review_article)
        builder.add_node("finish", self.finish)

        # 定义固定执行顺序：工作流启动后先生成候选选题。
        builder.add_edge(START, "generate_topics")
        # 选题生成完成后，进入人工选择节点。该节点会通过 interrupt 暂停。
        builder.add_edge("generate_topics", "select_topic")
        # 用户选好题并恢复流程后，进入文章生成节点。
        builder.add_edge("select_topic", "generate_article")
        # 文章生成并保存版本后，进入人工审核节点。这里会再次暂停。
        builder.add_edge("generate_article", "review_article")

        # 审核节点不是固定走向，需要读取用户提交的 decision 决定下一站。
        builder.add_conditional_edges(
            "review_article",
            # 从 state.review 中读取审核决定；没有值时默认按 approve 处理。
            lambda state: state.get("review", {}).get("decision", "approve"),
            # 通过则结束；退回或完全重写则回到文章生成节点，形成审核循环。
            {"approve": "finish", "edit_and_approve": "finish", "reject": "generate_article", "regenerate": "generate_article"},
        )
        # finish 更新数据库状态后，工作流抵达 LangGraph 的终点。
        builder.add_edge("finish", END)

        # 编译图并接入 checkpointer。checkpointer 让 interrupt 后的状态可以被恢复。
        self.graph = builder.compile(checkpointer=checkpointer)

    @staticmethod
    def config(thread_id: str, task_id: str, model_configuration_id: str | None = None) -> dict:
        """生成 LangGraph 每次调用都需要的配置。

        thread_id 相当于工作流存档编号。启动和恢复必须使用同一个编号，
        否则 LangGraph 无法找到之前 interrupt 时保存的 checkpoint。
        """
        return {
            "configurable": {"thread_id": thread_id},
            "run_name": "xiaohongshu-content-workflow",
            "tags": ["xiaohongshu", "content-workflow"],
            "metadata": {
                "task_id": task_id,
                "thread_id": thread_id,
                "model_configuration_id": model_configuration_id or "env-default",
            },
        }

    def start(self, task_id: str, instruction: str = "", llm_topic_count: int = 4, rag_topic_count: int = 3):
        """从 START 启动一个全新的内容工作流。"""
        # 每次重新启动都生成新 thread_id，避免错误恢复到旧工作流。
        thread_id = f"content-task:{task_id}:{uuid.uuid4()}"
        logger.info("content_workflow.start task_id=%s thread_id=%s", task_id, thread_id)
        # 打开一个短生命周期数据库会话。
        with self.session_factory() as db:
            # 根据前端传入的任务 ID 查询业务任务。
            task = db.get(ContentTask, task_id)
            if not task:
                raise ValueError("内容任务不存在")
            # 将工作流存档编号写入任务，后续 resume 会从这里取回。
            task.workflow_thread_id = thread_id
            model_configuration_id = task.model_configuration_id
            db.commit()
        # 初始 state 只存任务 ID 和本次补充指令；随后从 START 开始执行。
        try:
            result = self.graph.invoke({
                "task_id": task_id,
                "instruction": instruction,
                "llm_topic_count": llm_topic_count,
                "rag_topic_count": rag_topic_count,
            }, self.config(thread_id, task_id, model_configuration_id))
            logger.info("content_workflow.paused_or_finished task_id=%s thread_id=%s", task_id, thread_id)
            return result
        except Exception:
            logger.exception("content_workflow.start_failed task_id=%s thread_id=%s", task_id, thread_id)
            raise

    def start_stream(self, task_id: str, instruction: str = "", llm_topic_count: int = 4, rag_topic_count: int = 3):
        """启动主图并逐节点产生事件，包含选题子图内部节点。"""
        thread_id = f"content-task:{task_id}:{uuid.uuid4()}"
        with self.session_factory() as db:
            task = db.get(ContentTask, task_id)
            if not task:
                raise ValueError("内容任务不存在")
            task.workflow_thread_id = thread_id
            model_configuration_id = task.model_configuration_id
            db.commit()
        initial = {"task_id": task_id, "instruction": instruction, "llm_topic_count": llm_topic_count, "rag_topic_count": rag_topic_count}
        yield {"event": "started", "node": "START", "message": "工作流已启动"}
        try:
            # tasks 模式会在节点开始和结束时分别发事件；updates 只在节点结束后发，
            # LLM 调用期间前端会长时间没有反馈，看起来像一次性返回。
            for namespace, task_event in self.graph.stream(
                initial,
                self.config(thread_id, task_id, model_configuration_id),
                stream_mode="tasks",
                subgraphs=True,
            ):
                yield self._task_stream_event(namespace, task_event)
        except Exception as exc:
            self._mark_failed(task_id, exc)
            raise
        yield {"event": "completed", "node": "select_topic", "message": "候选选题已生成，等待人工选择"}

    def resume_stream(self, task_id: str, value: dict):
        """从 interrupt 恢复，并逐节点返回后续执行事件。"""
        with self.session_factory() as db:
            task = db.get(ContentTask, task_id)
            if not task or not task.workflow_thread_id:
                raise ValueError("任务没有可恢复的工作流")
            thread_id = task.workflow_thread_id
            model_configuration_id = task.model_configuration_id
        yield {"event": "started", "node": "resume", "message": "已恢复工作流"}
        try:
            for namespace, task_event in self.graph.stream(
                Command(resume=value),
                self.config(thread_id, task_id, model_configuration_id),
                stream_mode="tasks",
                subgraphs=True,
            ):
                yield self._task_stream_event(namespace, task_event)
        except Exception as exc:
            self._mark_failed(task_id, exc)
            raise
        yield {"event": "completed", "node": "review_article", "message": "文案已生成，等待人工审核"}

    @staticmethod
    def _node_message(node: str) -> str:
        return {
            "initialize": "正在初始化任务",
            "generate_llm_topics": "正在调用 LLM 生成选题",
            "retrieve_rag_topics": "正在从知识库召回选题",
            "merge_and_rank_topics": "正在合并、去重和排序",
            "persist_topics": "正在保存候选选题",
            "generate_topics": "选题子图执行完成",
            "select_topic": "已确认选题",
            "generate_article": "正在生成文章",
            "review_article": "文章已进入审核阶段",
            "__interrupt__": "工作流等待人工操作",
        }.get(node, f"正在执行 {node}")

    @classmethod
    def _task_stream_event(cls, namespace, task_event: dict) -> dict:
        """把 LangGraph task 开始/结束事件转换成前端使用的轻量 SSE 事件。"""
        node = task_event.get("name", "unknown")
        finished = "result" in task_event or "error" in task_event
        if finished:
            error = task_event.get("error")
            message = f"{node} 执行失败：{error}" if error else f"{cls._node_label(node)}已完成"
            event_name = "node_error" if error else "node_completed"
        else:
            message = cls._node_message(node)
            event_name = "node_started"
        return {
            "event": event_name,
            "node": node,
            "namespace": list(namespace),
            "message": message,
        }

    @staticmethod
    def _node_label(node: str) -> str:
        return {
            "initialize": "任务初始化",
            "generate_llm_topics": "LLM 选题生成",
            "retrieve_rag_topics": "知识库选题召回",
            "merge_and_rank_topics": "选题合并与排序",
            "persist_topics": "候选选题保存",
            "generate_topics": "选题子图",
            "select_topic": "选题确认",
            "generate_article": "文章生成",
            "review_article": "文章审核准备",
        }.get(node, node)

    def _mark_failed(self, task_id: str, exc: Exception) -> None:
        with self.session_factory() as db:
            task = db.get(ContentTask, task_id)
            if task:
                task.status = TaskStatus.failed
                task.current_stage = "failed"
                task.error_message = str(exc)
                db.commit()

    def resume(self, task_id: str, value: dict):
        """把人工选择或审核结果送回 interrupt，并继续执行原工作流。"""
        with self.session_factory() as db:
            task = db.get(ContentTask, task_id)
            # 没有 thread_id 表示任务从未启动，或者工作流存档已经丢失。
            if not task or not task.workflow_thread_id:
                raise ValueError("任务没有可恢复的工作流")
            thread_id = task.workflow_thread_id
            model_configuration_id = task.model_configuration_id
        # 只记录决定类型和字段名，不打印审核意见或其他用户正文。
        logger.info(
            "content_workflow.resume task_id=%s thread_id=%s decision=%s fields=%s",
            task_id,
            thread_id,
            value.get("decision", "topic_selection"),
            sorted(value.keys()),
        )
        # Command(resume=value) 会让上次 interrupt() 返回 value，然后继续执行该节点。
        try:
            result = self.graph.invoke(Command(resume=value), self.config(thread_id, task_id, model_configuration_id))
            logger.info("content_workflow.resumed task_id=%s thread_id=%s", task_id, thread_id)
            return result
        except Exception:
            logger.exception("content_workflow.resume_failed task_id=%s thread_id=%s", task_id, thread_id)
            raise

    def select_topic(self, state: ContentState) -> ContentState:
        """节点二：暂停工作流，等待用户选择一个候选选题。"""
        logger.info("content_workflow.interrupt node=select_topic task_id=%s reason=waiting_topic_selection", state["task_id"])
        # 第一个人工中断点。执行到这里时，LangGraph 保存 checkpoint 并暂停。
        # 前端提交 topic_id 后，resume() 会使 interrupt() 返回该字典。
        selection = interrupt({"kind": "topic_selection", "task_id": state["task_id"]})
        topic_id = selection["topic_id"]
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            topic = db.get(TopicCandidate, topic_id)
            # 除了检查记录存在，还要防止选择属于其他任务的候选项。
            if not task or not topic or topic.content_task_id != task.id:
                raise ValueError("候选选题无效")
            # 先把当前任务的所有候选项恢复为 candidate。
            db.query(TopicCandidate).filter(TopicCandidate.content_task_id == task.id).update({"status": "candidate"})
            # 再单独标记用户选择的候选项。
            topic.status = "selected"
            task.selected_topic_id = topic.id
            # 下一节点将生成文章，因此同步更新给前端看的业务状态。
            task.status = TaskStatus.generating_article
            task.current_stage = "generating_article"
            db.commit()
            logger.info(
                "content_workflow.node_complete node=select_topic task_id=%s topic_id=%s next=generate_article",
                task.id,
                topic_id,
            )
        # 将 topic_id 合并进图状态，后续 checkpoint 也会保留它。
        return {**state, "topic_id": topic_id}

    def generate_article(self, state: ContentState) -> ContentState:
        """节点三：根据选题生成文章；退回审核后也会重新进入此节点。"""
        logger.info(
            "content_workflow.node_enter node=generate_article task_id=%s revision=%s",
            state["task_id"],
            bool(state.get("review")),
        )
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            # selected_topic_id 存在业务表中，因此可从数据库恢复完整选题内容。
            topic = db.get(TopicCandidate, task.selected_topic_id) if task else None
            if not task or not topic:
                raise ValueError("未找到已选选题")

            # 第一次生成时 review 为空；审核退回时 review 包含 decision 和 comment。
            review = state.get("review", {})
            # 优先把审核意见作为修改指令；没有审核意见时使用启动阶段的补充指令。
            instruction = review.get("comment", "") or state.get("instruction", "")
            # 将数据库选题转换回 LLMProvider 所需的结构，然后生成文章。
            llm = self._llm_for_task(db, task)
            output = llm.generate_article(
                TopicOutput(topic.title, topic.summary, topic.target_reader, topic.reason, topic.score), instruction
            )
            self._save_usage(db, task.id, "generate_article", llm)

            # 一项内容任务只有一个 Article 主体，但可以拥有多个不可变版本。
            article = db.scalar(select(Article).where(Article.content_task_id == task.id))
            if not article:
                # 首次生成时创建文章主体。
                article = Article(content_task_id=task.id, selected_topic_id=topic.id)
                db.add(article)
                # flush 立即取得 article.id，但还不提交事务。
                db.flush()
            # 查询已有最大版本号，新版本在其基础上加一。
            next_version = (db.scalar(select(func.max(ArticleVersion.version_number)).where(ArticleVersion.article_id == article.id)) or 0) + 1
            # 第一版标记为 AI 初次生成，审核退回产生的后续版本标记为 AI 修订。
            source_type = "ai_revised" if next_version > 1 else "ai_generated"
            version = ArticleVersion(
                article_id=article.id,
                version_number=next_version,
                title=output.title,
                outline=output.outline,
                content=output.content,
                generation_instruction=instruction,
                source_type=source_type,
            )
            db.add(version)
            # flush 后才能把新 version.id 设置为文章的当前版本。
            db.flush()
            article.current_version_id = version.id
            article.status = "waiting_review"
            # 通知前端文章已经生成完毕，可以显示审核界面。
            task.status = TaskStatus.waiting_article_review
            task.current_stage = "waiting_article_review"
            db.commit()
            article_id = article.id
            logger.info(
                "content_workflow.node_complete node=generate_article task_id=%s article_id=%s version=%d next=review_article",
                task.id,
                article_id,
                next_version,
            )
        # 清空旧 review 非常重要：否则审核退回后可能重复使用上一次 decision 继续路由。
        return {**state, "article_id": article_id, "review": {}}

    def review_article(self, state: ContentState) -> ContentState:
        """节点四：暂停工作流，等待用户审核当前文章版本。"""
        logger.info(
            "content_workflow.interrupt node=review_article task_id=%s article_id=%s reason=waiting_article_review",
            state["task_id"],
            state["article_id"],
        )
        # 第二个人工中断点。前端可以提交 approve、edit_and_approve、reject 或 regenerate。
        review = interrupt({
            "kind": "article_review",
            "task_id": state["task_id"],
            "article_id": state["article_id"]
        })
        logger.info(
            "content_workflow.review_received task_id=%s article_id=%s decision=%s",
            state["task_id"],
            state["article_id"],
            review.get("decision", "unknown"),
        )
        # 把审核结果写入 state；节点结束后 conditional_edges 会读取 decision 决定分支。
        return {**state, "review": review}

    def finish(self, state: ContentState) -> ContentState:
        """节点五：审核通过后更新最终业务状态。"""
        logger.info("content_workflow.node_enter node=finish task_id=%s", state["task_id"])
        with self.session_factory() as db:
            task = db.get(ContentTask, state["task_id"])
            article = db.scalar(select(Article).where(Article.content_task_id == state["task_id"]))
            if task:
                # completed 表示核心文章工作流结束，后续可以生成图片和平台版本。
                task.status = TaskStatus.completed
                task.current_stage = "completed"
            if article:
                # 当前文章版本被确认为可用于下游生产的终稿。
                article.status = "approved"
            db.commit()
        logger.info("content_workflow.node_complete node=finish task_id=%s next=END", state["task_id"])
        # finish 后沿固定边到 END，此返回值作为工作流最终 state。
        return state

    def _llm_for_task(self, db: Session, task: ContentTask) -> LLMProvider:
        primary = db.get(ModelConfiguration, task.model_configuration_id) if task.model_configuration_id else None
        # 自动化测试必须保持完全离线；显式选择模型的专项测试仍会经过下面的动态解析。
        if get_settings().app_env == "test" and not primary:
            return self.llm
        # 个人模型只允许作为任务明确选择的首选项；自动兜底仅使用系统模型，
        # 避免错误使用其他用户保存在数据库中的私有密钥。
        system_models = list(db.scalars(
            select(ModelConfiguration)
            .where(
                ModelConfiguration.owner_user_id.is_(None),
                ModelConfiguration.capability == "text",
                ModelConfiguration.enabled.is_(True),
                ModelConfiguration.protocol.in_(["openai_compatible", "anthropic_compatible"]),
            )
            .order_by(
                # 阿里 0731 是额度兜底，优先于当前已出现额度不足的服务。
                case((ModelConfiguration.model == "deepseek-v4-flash-0731", 0), else_=1),
                ModelConfiguration.is_default.desc(),
                ModelConfiguration.created_at.asc(),
            )
        ))
        ordered = ([primary] if primary else []) + system_models
        providers, seen = [], set()
        for model in ordered:
            if not model or model.id in seen:
                continue
            seen.add(model.id)
            providers.append(provider_from_model_configuration(model))
        if not providers:
            return self.llm
        return FallbackLLMProvider(providers)

    def _save_usage(self, db: Session, task_id: str, operation: str, llm: LLMProvider | None = None) -> None:
        """将刚完成的模型调用统计写入业务库，正文和 Prompt 不进入统计表。"""
        usage = (llm or self.llm).consume_usage()
        if not usage:
            logger.warning("llm_usage.missing task_id=%s operation=%s", task_id, operation)
            return
        db.add(ModelUsageEvent(
            content_task_id=task_id,
            provider=usage.provider,
            model=usage.model,
            operation=operation,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost=0,
            latency_ms=usage.latency_ms,
            status=usage.status,
        ))
        logger.info(
            "llm_usage.recorded task_id=%s operation=%s model=%s input_tokens=%d output_tokens=%d total_tokens=%d latency_ms=%d",
            task_id, operation, usage.model, usage.input_tokens, usage.output_tokens,
            usage.input_tokens + usage.output_tokens, usage.latency_ms,
        )
