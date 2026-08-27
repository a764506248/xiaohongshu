export type TaskStatus =
  | 'draft'
  | 'generating_topics'
  | 'waiting_topic_selection'
  | 'generating_article'
  | 'waiting_article_review'
  | 'completed'
  | 'failed'

export interface ContentTask {
  id: string
  title: string
  requirement: string
  target_audience: string
  model_configuration_id: string | null
  status: TaskStatus
  current_stage: string
  selected_topic_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface Topic {
  id: string
  title: string
  summary: string
  target_reader: string
  reason: string
  score: number
  status: string
}

export interface ArticleVersion {
  id: string
  version_number: number
  title: string
  outline: string
  content: string
  generation_instruction: string
  source_type: string
  created_at: string
}

export interface Article {
  id: string
  content_task_id: string
  status: string
  current_version_id: string | null
  versions: ArticleVersion[]
}

export interface Review {
  id: string
  decision: string
  comment: string
  reviewer_id: string
  created_at: string
  article_version_id: string
}

export interface ImageVersion {
  id: string
  version_number: number
  public_url: string
  source_type: string
  width: number
  height: number
  file_hash: string
  created_at: string
}

export interface ImagePage {
  id: string
  page_number: number
  title: string
  body: string
  purpose: string
  visual_description: string
  template: 'editorial' | 'dark' | 'warm'
  current_version_id: string | null
  versions: ImageVersion[]
}

export interface XiaohongshuPackage {
  id: string
  content_task_id: string
  article_version_id: string
  title: string
  body: string
  tags: string
  status: string
  validation_message: string
  pages: ImagePage[]
  created_at: string
  updated_at: string
}
export interface ChannelVariant { id:string; content_task_id:string; article_version_id:string; channel:string; title:string; summary:string; body:string; html_content:string; cover_url:string; tags:string; status:string; created_at:string; updated_at:string }
export interface ChannelAccount { id:string; name:string; channel:string; mode:string; credential_reference:string; status:string; created_at:string }
export interface PublishJob { id:string; channel_variant_id:string; channel_account_id:string; idempotency_key:string; approval_status:string; status:string; scheduled_at:string|null; published_at:string|null; external_post_id:string|null; retry_count:number; max_retries:number; error_message:string|null; created_at:string; updated_at:string; channel?:string|null; content_title?:string|null; account_name?:string|null; account_mode?:string|null }
export interface PreferenceSignal { id:string; signal_type:string; signal_value:string; weight:number; sample_count:number; updated_at:string }
export interface AnalyticsSummary { published_posts:number; total_views:number; total_interactions:number; average_score:number; model_calls:number; total_input_tokens:number; total_output_tokens:number; total_tokens:number; total_latency_ms:number; estimated_model_cost:number; top_signals:PreferenceSignal[] }
export interface ContentMetric { id:string; publish_job_id:string; content_title:string; channel:string; external_post_id:string|null; views:number; likes:number; favorites:number; comments:number; shares:number; follower_gain:number; performance_score:number; collected_at:string }
export interface ModelUsage { id:string; content_task_id:string|null; provider:string; model:string; operation:string; input_tokens:number; output_tokens:number; estimated_cost:number; latency_ms:number; status:string; created_at:string }
export interface TokenUsagePoint { period:string; calls:number; input_tokens:number; output_tokens:number; total_tokens:number; latency_ms:number }
export interface TokenUsageReport { granularity:'day'|'month'|'year'; start_at:string; end_at:string; calls:number; input_tokens:number; output_tokens:number; total_tokens:number; points:TokenUsagePoint[] }
