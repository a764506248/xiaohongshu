import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { contentApi } from '../api/content'
import { Notice } from '../components/Notice'
import { StatusBadge } from '../components/StatusBadge'
import type { ContentTask } from '../types'

export function TaskList() {
  const [tasks, setTasks] = useState<ContentTask[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    contentApi.listTasks().then(setTasks).catch((e: Error) => setError(e.message)).finally(() => setLoading(false))
  }, [])

  return <main>
    <div className="page-heading">
      <div><p className="eyebrow">CONTENT OPERATIONS</p><h1>内容任务</h1><p>从选题到审核，集中管理每日内容生产。</p></div>
      <Link className="button primary" to="/tasks/new">创建任务</Link>
    </div>
    {error && <Notice>{error}</Notice>}
    {loading ? <div className="empty">正在加载任务…</div> : tasks.length === 0 ?
      <div className="empty"><h2>还没有内容任务</h2><p>创建第一个任务，开始生成候选选题。</p></div> :
      <div className="task-grid">{tasks.map(task =>
        <Link className="task-card" to={`/tasks/${task.id}`} key={task.id}>
          <div className="card-top"><StatusBadge status={task.status}/><time>{new Date(task.created_at).toLocaleDateString('zh-CN')}</time></div>
          <h2>{task.title}</h2><p>{task.requirement || '暂无补充要求'}</p>
          <div className="card-footer"><span>{task.target_audience}</span><span>查看 →</span></div>
        </Link>)}</div>}
  </main>
}

