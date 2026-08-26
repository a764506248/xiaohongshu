from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import TaskStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ContentTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="内容方向或主题", examples=["LangGraph 人工审核实战"])
    requirement: str = Field(default="", description="语气、重点、篇幅等补充要求", examples=["表达克制，突出可操作步骤"])
    target_audience: str = Field(default="AI 编程学习者", description="文章的目标读者", examples=["AI 应用开发初学者"])


class ContentTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200, description="新的内容方向；不传则保持不变")
    requirement: str | None = Field(default=None, description="新的补充要求；不传则保持不变")
    target_audience: str | None = Field(default=None, description="新的目标读者；不传则保持不变")


class ContentTaskRead(ORMModel):
    id: str = Field(description="内容任务 UUID")
    title: str = Field(description="内容方向或主题")
    requirement: str = Field(description="运营人员填写的补充要求")
    target_audience: str = Field(description="目标读者")
    status: TaskStatus = Field(description="业务状态，前端根据该字段展示当前操作")
    current_stage: str = Field(description="工作流当前阶段，通常与 status 对应")
    selected_topic_id: str | None = Field(description="已选候选选题 ID；尚未选择时为 null")
    error_message: str | None = Field(description="最近一次执行错误；没有错误时为 null")
    created_at: datetime = Field(description="任务创建时间，UTC")
    updated_at: datetime = Field(description="任务最后更新时间，UTC")


class TopicRead(ORMModel):
    id: str = Field(description="候选选题 UUID")
    content_task_id: str = Field(description="所属内容任务 ID")
    title: str = Field(description="候选选题标题")
    summary: str = Field(description="选题内容概要")
    target_reader: str = Field(description="该选题适合的目标读者")
    reason: str = Field(description="AI 推荐该选题的理由")
    score: float = Field(description="AI 综合评分，范围 0～100")
    status: str = Field(description="candidate 表示候选，selected 表示已被选择")


class TopicSelection(BaseModel):
    topic_id: str = Field(description="候选选题 ID，可从查询候选选题接口获得")


class GenerateRequest(BaseModel):
    instruction: str = Field(default="", description="仅对本次生成生效的补充要求", examples=["优先提供实战和避坑类选题"])
    llm_topic_count: int = Field(default=4, ge=1, le=20, description="由大模型生成的候选数量")
    rag_topic_count: int = Field(default=3, ge=0, le=20, description="从历史选题知识库召回的候选数量")


class ArticleVersionRead(ORMModel):
    id: str = Field(description="文章版本 UUID")
    article_id: str = Field(description="所属文章主体 ID")
    version_number: int = Field(description="递增版本号，从 1 开始")
    title: str = Field(description="该版本文章标题")
    outline: str = Field(description="从 Markdown 二级标题提取的文章提纲")
    content: str = Field(description="Markdown 格式的完整正文")
    generation_instruction: str = Field(description="生成或修订该版本时使用的补充要求")
    source_type: str = Field(description="版本来源：ai_generated、ai_revised 或 human_edited")
    created_at: datetime = Field(description="版本创建时间，UTC")


class ArticleRead(ORMModel):
    id: str = Field(description="文章主体 UUID")
    content_task_id: str = Field(description="所属内容任务 ID")
    selected_topic_id: str = Field(description="生成文章所依据的候选选题 ID")
    status: str = Field(description="文章状态：draft、waiting_review 或 approved")
    current_version_id: str | None = Field(description="当前审核或发布使用的文章版本 ID")
    versions: list[ArticleVersionRead] = Field(description="文章的全部历史版本，按版本号升序排列")


class HumanEdit(BaseModel):
    title: str = Field(min_length=1, max_length=250, description="人工修改后的文章标题")
    content: str = Field(min_length=1, description="人工修改后的 Markdown 正文")


class ReviewRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100, description="客户端生成的唯一幂等 ID", examples=["review-20260825-001"])
    decision: Literal["approve", "reject", "edit_and_approve", "regenerate"] = Field(description="审核决定")
    comment: str = Field(default="", description="审核意见；reject 时建议必填")
    reviewer_id: str = Field(default="operator", description="审核人标识")
    edited_title: str | None = Field(default=None, description="edit_and_approve 时提交的最终标题")
    edited_content: str | None = Field(default=None, description="edit_and_approve 时提交的最终正文")


class ReviewRead(ORMModel):
    id: str = Field(description="审核记录 UUID")
    request_id: str = Field(description="客户端幂等请求 ID")
    content_task_id: str = Field(description="所属内容任务 ID")
    article_version_id: str = Field(description="本次审核针对的文章版本 ID")
    decision: str = Field(description="审核决定：approve、reject、edit_and_approve 或 regenerate")
    comment: str = Field(description="审核意见")
    reviewer_id: str = Field(description="审核人标识")
    created_at: datetime = Field(description="审核时间，UTC")


class OperationResult(BaseModel):
    status: str = Field(description="操作完成后的任务阶段")
    task_id: str = Field(description="内容任务 ID")
    detail: str = Field(default="", description="可选的操作补充说明")


class ImageVersionRead(ORMModel):
    id: str = Field(description="图片版本 UUID")
    version_number: int = Field(description="该页面的递增图片版本号")
    public_url: str = Field(description="前端访问图片的相对 URL，以 /media 开头")
    source_type: str = Field(description="版本来源：generated、regenerated、text_edited 或 uploaded")
    width: int = Field(description="图片宽度，单位像素")
    height: int = Field(description="图片高度，单位像素")
    file_hash: str = Field(description="图片文件 SHA-256，用于缓存刷新和完整性检查")
    created_at: datetime = Field(description="图片版本创建时间，UTC")


class ImagePageRead(ORMModel):
    id: str = Field(description="图片页面 UUID")
    page_number: int = Field(description="当前内容包中的页面顺序，从 1 开始")
    title: str = Field(description="图片上显示的主标题")
    body: str = Field(description="图片上显示的精简正文")
    purpose: str = Field(description="页面用途，例如封面、核心内容或行动建议")
    visual_description: str = Field(description="图片视觉策划描述，供未来图片模型使用")
    template: str = Field(description="当前视觉模板：editorial、dark 或 warm")
    current_version_id: str | None = Field(description="当前展示和导出的图片版本 ID")
    versions: list[ImageVersionRead] = Field(description="该页面的全部历史图片版本")


class XiaohongshuPackageRead(ORMModel):
    id: str = Field(description="小红书内容包 UUID")
    content_task_id: str = Field(description="所属内容任务 ID")
    article_version_id: str = Field(description="生成该内容包时使用的已审核文章版本 ID")
    title: str = Field(description="小红书发布标题")
    body: str = Field(description="小红书发布正文")
    tags: str = Field(description="空格分隔的话题标签")
    status: str = Field(description="内容包状态，当前 ready 表示可编辑和导出")
    validation_message: str = Field(description="内容长度和资源完整性的校验结果")
    pages: list[ImagePageRead] = Field(description="内容包的 3～5 个图片页面，按 page_number 排序")
    created_at: datetime = Field(description="内容包创建时间，UTC")
    updated_at: datetime = Field(description="内容包最后更新时间，UTC")


class ImagePageUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120, description="图片上的主标题")
    body: str = Field(min_length=1, max_length=500, description="图片上的精简正文")
    template: Literal["editorial", "dark", "warm"] = Field(default="editorial", description="视觉模板：浅色编辑部、深色技术感或温暖教育风")


class PageOrderUpdate(BaseModel):
    page_ids: list[str] = Field(min_length=3, max_length=5, description="内容包全部页面 ID，按期望顺序排列")


class XiaohongshuPackageUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100, description="小红书发布标题")
    body: str = Field(min_length=1, max_length=3000, description="小红书发布正文")
    tags: str = Field(default="", max_length=500, description="使用空格分隔的话题标签", examples=["#AI编程 #LangGraph #AI应用开发"])


class ChannelAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="运营人员可识别的账号名称")
    channel: Literal["xiaohongshu", "wechat"] = Field(description="内容平台")
    mode: Literal["manual", "mock"] = Field(default="manual", description="manual 表示人工发布，mock 用于本地自动发布演示")
    credential_reference: str = Field(default="", description="外部密钥管理器中的凭证引用；不要直接提交明文密钥")


class ChannelAccountRead(ORMModel):
    id: str = Field(description="平台账号 UUID")
    name: str = Field(description="账号名称")
    channel: str = Field(description="平台：xiaohongshu 或 wechat")
    mode: str = Field(description="发布模式：manual 或 mock")
    credential_reference: str = Field(description="凭证引用，不包含实际密钥")
    status: str = Field(description="账号状态")
    created_at: datetime = Field(description="创建时间，UTC")


class ChannelVariantUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="平台版本标题")
    summary: str = Field(default="", max_length=500, description="平台摘要")
    body: str = Field(min_length=1, description="平台正文，支持 Markdown")
    tags: str = Field(default="", max_length=500, description="平台话题标签")
    cover_url: str = Field(default="", description="封面图片 URL")


class ChannelVariantRead(ORMModel):
    id: str = Field(description="平台内容版本 UUID")
    content_task_id: str = Field(description="来源内容任务 ID")
    article_version_id: str = Field(description="来源文章版本 ID")
    channel: str = Field(description="目标平台")
    title: str = Field(description="平台标题")
    summary: str = Field(description="平台摘要")
    body: str = Field(description="Markdown 或纯文本正文")
    html_content: str = Field(description="微信公众号预览使用的安全 HTML")
    cover_url: str = Field(description="封面 URL")
    tags: str = Field(description="话题标签")
    status: str = Field(description="draft、ready 或 published")
    created_at: datetime = Field(description="创建时间，UTC")
    updated_at: datetime = Field(description="更新时间，UTC")


class PublishJobCreate(BaseModel):
    channel_variant_id: str = Field(description="待发布的平台版本 ID")
    channel_account_id: str = Field(description="目标平台账号 ID")
    idempotency_key: str = Field(min_length=1, max_length=120, description="客户端唯一键，防止重复创建发布任务")
    scheduled_at: datetime | None = Field(default=None, description="预约发布时间，UTC；不填表示审批后立即可执行")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大自动重试次数")


class PublishDecision(BaseModel):
    decision: Literal["approve", "reject"] = Field(description="发布审批决定")
    comment: str = Field(default="", description="审批备注或拒绝原因")


class PublishJobRead(ORMModel):
    id: str = Field(description="发布任务 UUID")
    channel_variant_id: str = Field(description="平台内容版本 ID")
    channel_account_id: str = Field(description="平台账号 ID")
    idempotency_key: str = Field(description="发布幂等键")
    approval_status: str = Field(description="pending、approved 或 rejected")
    status: str = Field(description="pending_approval、scheduled、publishing、published、failed 或 rejected")
    scheduled_at: datetime | None = Field(description="预约发布时间，UTC")
    published_at: datetime | None = Field(description="成功发布时间，UTC")
    external_post_id: str | None = Field(description="平台返回的内容 ID；manual 模式可由运营人员填写")
    retry_count: int = Field(description="已经执行的重试次数")
    max_retries: int = Field(description="最大重试次数")
    error_message: str | None = Field(description="最近一次发布错误")
    created_at: datetime = Field(description="创建时间，UTC")
    updated_at: datetime = Field(description="更新时间，UTC")
    channel: str | None = Field(default=None, description="发布平台")
    content_title: str | None = Field(default=None, description="待发布内容标题")
    account_name: str | None = Field(default=None, description="目标账号名称")
    account_mode: str | None = Field(default=None, description="账号发布模式")


class ManualPublishComplete(BaseModel):
    external_post_id: str = Field(min_length=1, max_length=160, description="人工发布后填写的平台内容 ID 或 URL")


class MetricCreate(BaseModel):
    views: int = Field(default=0, ge=0, description="阅读或曝光数")
    likes: int = Field(default=0, ge=0, description="点赞数")
    favorites: int = Field(default=0, ge=0, description="收藏数")
    comments: int = Field(default=0, ge=0, description="评论数")
    shares: int = Field(default=0, ge=0, description="分享数")
    follower_gain: int = Field(default=0, description="本条内容带来的粉丝净增长")


class MetricRead(ORMModel):
    id: str = Field(description="指标快照 UUID")
    publish_job_id: str = Field(description="所属发布任务 ID")
    views: int = Field(description="阅读或曝光数")
    likes: int = Field(description="点赞数")
    favorites: int = Field(description="收藏数")
    comments: int = Field(description="评论数")
    shares: int = Field(description="分享数")
    follower_gain: int = Field(description="粉丝净增长")
    performance_score: float = Field(description="根据互动率、收藏、分享和涨粉计算的 0～100 分")
    collected_at: datetime = Field(description="指标采集时间，UTC")


class PreferenceSignalRead(ORMModel):
    id: str = Field(description="偏好信号 UUID")
    signal_type: str = Field(description="信号类型，例如 channel 或 tag")
    signal_value: str = Field(description="平台或标签值")
    weight: float = Field(description="综合表现权重")
    sample_count: int = Field(description="参与计算的样本数")
    updated_at: datetime = Field(description="最后更新时间，UTC")


class TopicDuplicateRead(BaseModel):
    title: str = Field(description="历史平台版本标题")
    channel: str = Field(description="历史内容所属平台")
    similarity: float = Field(description="标题相似度，范围 0～1")


class ModelUsageRead(ORMModel):
    id: str = Field(description="模型调用事件 UUID")
    content_task_id: str | None = Field(description="关联内容任务 ID")
    provider: str = Field(description="模型服务商")
    model: str = Field(description="模型名称")
    operation: str = Field(description="调用场景，例如 generate_topics")
    input_tokens: int = Field(description="输入 token 数")
    output_tokens: int = Field(description="输出 token 数")
    estimated_cost: float = Field(description="估算调用成本")
    latency_ms: int = Field(description="调用耗时，毫秒")
    status: str = Field(description="调用状态")
    created_at: datetime = Field(description="调用时间，UTC")


class ModelConfigurationRead(ORMModel):
    id: str
    owner_user_id: str | None
    name: str
    provider: str
    model: str
    capability: str
    protocol: str
    base_url: str
    has_api_key: bool
    is_system: bool
    enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ModelConfigurationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider: str | None = Field(default=None, min_length=1, max_length=50)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    capability: Literal["text", "image", "image_to_video"] | None = None
    protocol: Literal["openai_compatible", "dashscope_native", "anthropic_compatible"] | None = None
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    api_key: str | None = Field(default=None, max_length=1000, description="留空表示不修改现有密钥")
    enabled: bool = True
    is_default: bool = False


class ModelConfigurationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=120)
    capability: Literal["text", "image", "image_to_video"]
    protocol: Literal["openai_compatible", "dashscope_native", "anthropic_compatible"]
    base_url: str = Field(min_length=8, max_length=500)
    api_key: str = Field(min_length=1, max_length=1000)
    enabled: bool = True


class ModelTestRequest(BaseModel):
    prompt: str = Field(default="一张简洁的 AI 编程课程海报，红黑配色，竖版构图", min_length=2, max_length=1000)


class ModelTestResult(BaseModel):
    status: str
    model: str
    output_url: str | None = None
    output_text: str | None = None
    latency_ms: int


class PromptVersionRead(ORMModel):
    id: str
    version_number: int
    system_prompt: str
    user_prompt_template: str
    variables_json: str
    change_note: str
    created_by: str | None
    created_at: datetime


class PromptTemplateRead(ORMModel):
    id: str
    owner_user_id: str | None
    name: str
    prompt_key: str
    tags: list[str]
    scene: str
    model_capability: str
    description: str
    status: str
    is_default: bool
    is_system: bool
    current_version: PromptVersionRead | None
    created_at: datetime
    updated_at: datetime


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    prompt_key: str = Field(min_length=2, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    tags: list[str] = Field(default_factory=list, max_length=20)
    scene: str = Field(min_length=1, max_length=60)
    model_capability: Literal["text", "image", "image_to_video"] = "text"
    description: str = Field(default="", max_length=1000)
    system_prompt: str = ""
    user_prompt_template: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    change_note: str = Field(default="创建初始版本", max_length=300)
    status: Literal["draft", "enabled", "disabled"] = "enabled"
    is_default: bool = False


class PromptTemplateUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=20)
    scene: str = Field(min_length=1, max_length=60)
    model_capability: Literal["text", "image", "image_to_video"] = "text"
    description: str = Field(default="", max_length=1000)
    system_prompt: str = ""
    user_prompt_template: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    change_note: str = Field(default="更新 Prompt", max_length=300)
    status: Literal["draft", "enabled", "disabled"] = "enabled"
    is_default: bool = False


class PromptRollbackRequest(BaseModel):
    version_number: int = Field(ge=1)
    change_note: str = Field(default="回滚历史版本", max_length=300)


class TokenUsagePoint(BaseModel):
    period: str = Field(description="统计周期：日为 YYYY-MM-DD，月为 YYYY-MM，年为 YYYY")
    calls: int = Field(description="该周期模型调用次数")
    input_tokens: int = Field(description="该周期输入 Token")
    output_tokens: int = Field(description="该周期输出 Token")
    total_tokens: int = Field(description="该周期总 Token")
    latency_ms: int = Field(description="该周期累计响应耗时，毫秒")


class TokenUsageReport(BaseModel):
    granularity: Literal["day", "month", "year"] = Field(description="聚合粒度")
    start_at: datetime = Field(description="查询开始时间，UTC")
    end_at: datetime = Field(description="查询结束时间，UTC")
    calls: int = Field(description="所选区间调用次数")
    input_tokens: int = Field(description="所选区间输入 Token")
    output_tokens: int = Field(description="所选区间输出 Token")
    total_tokens: int = Field(description="所选区间总 Token")
    points: list[TokenUsagePoint] = Field(description="按统计粒度排列的时间序列")


class AnalyticsSummary(BaseModel):
    published_posts: int = Field(description="已发布内容数量")
    total_views: int = Field(description="累计阅读或曝光")
    total_interactions: int = Field(description="点赞、收藏、评论和分享总和")
    average_score: float = Field(description="全部指标快照的平均表现分")
    model_calls: int = Field(description="已记录模型调用次数")
    total_input_tokens: int = Field(description="模型累计输入 Token")
    total_output_tokens: int = Field(description="模型累计输出 Token")
    total_tokens: int = Field(description="模型累计总 Token")
    total_latency_ms: int = Field(description="模型调用累计耗时，毫秒")
    estimated_model_cost: float = Field(description="模型估算成本")
    top_signals: list[PreferenceSignalRead] = Field(description="当前权重最高的偏好信号")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80, description="登录用户名", examples=["admin"])
    password: str = Field(min_length=6, max_length=128, description="登录密码")


class UserRead(ORMModel):
    id: str = Field(description="用户 UUID")
    username: str = Field(description="登录用户名")
    display_name: str = Field(description="页面显示名称")
    role: str = Field(description="用户角色")
    status: str = Field(description="账号状态")
    created_at: datetime = Field(description="账号创建时间，UTC")
    last_login_at: datetime | None = Field(description="最近登录时间，UTC")
    permission_codes: list[str] = Field(description="用户拥有的权限码")


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern="^[a-zA-Z0-9_.-]+$", description="登录用户名")
    display_name: str = Field(min_length=1, max_length=120, description="显示名称")
    password: str = Field(min_length=6, max_length=128, description="初始密码")
    role: Literal["admin", "operator"] = Field(default="operator", description="用户角色")
    permission_codes: list[str] = Field(default_factory=list, description="分配给用户的权限码")


class UserUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120, description="显示名称")
    role: Literal["admin", "operator"] = Field(description="用户角色")
    status: Literal["active", "disabled"] = Field(description="账号状态")
    permission_codes: list[str] = Field(default_factory=list, description="分配给用户的权限码")


class PasswordReset(BaseModel):
    password: str = Field(min_length=6, max_length=128, description="新密码")


class LoginResponse(BaseModel):
    access_token: str = Field(description="后续请求使用的 Bearer 令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="令牌有效期，秒")
    user: UserRead = Field(description="当前登录用户")
