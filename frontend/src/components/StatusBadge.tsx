import type { TaskStatus } from '../types'

const labels: Record<TaskStatus, string> = {
  draft: '待开始',
  generating_topics: '生成选题中',
  waiting_topic_selection: '待选择选题',
  generating_article: '生成文案中',
  waiting_article_review: '待审核',
  completed: '已完成',
  failed: '失败',
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  return <span className={`status status-${status}`}>{labels[status]}</span>
}

