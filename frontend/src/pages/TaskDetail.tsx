import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { contentApi } from '../api/content'
import { Notice } from '../components/Notice'
import { StatusBadge } from '../components/StatusBadge'
import type { Article, ContentTask, Review, Topic } from '../types'

export function TaskDetail() {
  const { id = '' } = useParams()
  const [task, setTask] = useState<ContentTask | null>(null)
  const [topics, setTopics] = useState<Topic[]>([])
  const [article, setArticle] = useState<Article | null>(null)
  const [reviews, setReviews] = useState<Review[]>([])
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [comment, setComment] = useState('')
  const [instruction, setInstruction] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    const nextTask = await contentApi.getTask(id); setTask(nextTask)
    if (nextTask.status === 'waiting_topic_selection') setTopics(await contentApi.getTopics(id))
    if (['waiting_article_review', 'completed'].includes(nextTask.status)) {
      const nextArticle = await contentApi.getArticle(id); setArticle(nextArticle)
      const current = nextArticle.versions.find(v => v.id === nextArticle.current_version_id) ?? nextArticle.versions.at(-1)
      if (current) { setTitle(current.title); setContent(current.content) }
      setReviews(await contentApi.getReviews(id))
    }
  }, [id])

  useEffect(() => { load().catch((e: Error) => setError(e.message)) }, [load])
  const currentVersion = useMemo(() => article?.versions.find(v => v.id === article.current_version_id) ?? article?.versions.at(-1), [article])

  async function action(name: string, fn: () => Promise<unknown>) {
    setBusy(name); setError('')
    try { await fn(); await load() } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }

  if (!task) return <main><div className="empty">正在加载任务…</div>{error && <Notice>{error}</Notice>}</main>

  return <main>
    <Link className="back" to="/">← 返回任务列表</Link>
    <div className="page-heading"><div><p className="eyebrow">CONTENT TASK</p><h1>{task.title}</h1><p>{task.requirement || '暂无补充要求'} · {task.target_audience}</p></div><StatusBadge status={task.status}/></div>
    {error && <Notice>{error}</Notice>}{task.error_message && <Notice>{task.error_message}</Notice>}

    {task.status === 'draft' && <section className="panel centered"><span className="step-number">01</span><h2>生成候选选题</h2><p>AI 将从实战、避坑、案例和工具对比等角度提供候选方案。</p>
      <textarea rows={3} value={instruction} onChange={e => setInstruction(e.target.value)} placeholder="可选：补充本次选题要求" />
      <button className="button primary" disabled={!!busy} onClick={() => action('topics', () => contentApi.generateTopics(id, instruction))}>{busy ? '生成中…' : '生成候选选题'}</button></section>}

    {task.status === 'waiting_topic_selection' && <section><div className="section-heading"><div><span className="step-number">02</span><h2>选择一个选题</h2></div><button className="button secondary" disabled={!!busy} onClick={() => action('topics', () => contentApi.generateTopics(id, instruction))}>重新生成</button></div>
      <div className="topic-grid">{topics.map(topic => <article className="topic-card" key={topic.id}><div className="score">{topic.score.toFixed(0)}</div><h3>{topic.title}</h3><p>{topic.summary}</p><dl><dt>目标读者</dt><dd>{topic.target_reader}</dd><dt>推荐理由</dt><dd>{topic.reason}</dd></dl><button className="button primary" disabled={!!busy} onClick={() => action('select', () => contentApi.selectTopic(id, topic.id))}>{busy === 'select' ? '生成文案中…' : '选择并生成文案'}</button></article>)}</div></section>}

    {task.status === 'waiting_article_review' && article && currentVersion && <section className="workspace">
      <div className="editor panel"><div className="section-heading"><div><span className="step-number">03</span><h2>审核文案</h2></div><span>版本 {currentVersion.version_number}</span></div>
        <label>标题<input value={title} onChange={e => setTitle(e.target.value)} /></label><label>正文<textarea className="article-editor" value={content} onChange={e => setContent(e.target.value)} /></label>
        <button className="button secondary" disabled={!!busy} onClick={() => action('save', () => contentApi.saveVersion(article.id, title, content))}>保存为新版本</button></div>
      <aside className="panel review-panel"><h2>审核决定</h2><label>审核意见<textarea rows={5} value={comment} onChange={e => setComment(e.target.value)} placeholder="退回时请说明修改方向" /></label>
        <button className="button primary" disabled={!!busy} onClick={() => action('approve', () => contentApi.review(id, { request_id: crypto.randomUUID(), decision: 'approve', comment }))}>通过当前版本</button>
        <button className="button secondary" disabled={!!busy} onClick={() => action('edit', () => contentApi.review(id, { request_id: crypto.randomUUID(), decision: 'edit_and_approve', comment, edited_title: title, edited_content: content }))}>修改后通过</button>
        <button className="button secondary" disabled={!!busy || !comment.trim()} onClick={() => action('reject', () => contentApi.review(id, { request_id: crypto.randomUUID(), decision: 'reject', comment }))}>退回 AI 修改</button>
        <button className="button text-danger" disabled={!!busy} onClick={() => action('regenerate', () => contentApi.review(id, { request_id: crypto.randomUUID(), decision: 'regenerate', comment }))}>完全重新生成</button></aside></section>}

    {task.status === 'completed' && article && <section className="panel"><span className="step-number success">✓</span><h2>内容已审核完成</h2><p>当前版本已确认为最终稿，后续可进入图片与小红书内容包阶段。</p><div className="final-article"><h1>{title}</h1><pre>{content}</pre></div></section>}

    {reviews.length > 0 && <section className="history"><h2>审核记录</h2>{reviews.map(r => <div className="history-row" key={r.id}><strong>{r.decision}</strong><span>{r.comment || '无备注'}</span><time>{new Date(r.created_at).toLocaleString('zh-CN')}</time></div>)}</section>}
  </main>
}

