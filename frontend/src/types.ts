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

