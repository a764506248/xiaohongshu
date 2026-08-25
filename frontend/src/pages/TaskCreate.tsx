import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { contentApi } from '../api/content'
import { Notice } from '../components/Notice'

export function TaskCreate() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [requirement, setRequirement] = useState('')
  const [audience, setAudience] = useState('AI 应用开发初学者')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError('')
    try {
      const task = await contentApi.createTask({ title, requirement, target_audience: audience })
      navigate(`/tasks/${task.id}`)
    } catch (e) { setError((e as Error).message) } finally { setSaving(false) }
  }

  return <main className="narrow">
    <Link className="back" to="/">← 返回任务列表</Link>
    <div className="page-heading"><div><p className="eyebrow">NEW TASK</p><h1>创建内容任务</h1><p>先定义主题和受众，下一步再由 AI 提供候选选题。</p></div></div>
    {error && <Notice>{error}</Notice>}
    <form className="panel form" onSubmit={submit}>
      <label>内容方向<input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} placeholder="例如：LangGraph 人工审核实战" /></label>
      <label>目标受众<input value={audience} onChange={e => setAudience(e.target.value)} /></label>
      <label>补充要求<textarea rows={6} value={requirement} onChange={e => setRequirement(e.target.value)} placeholder="希望突出哪些观点、语气或案例？" /></label>
      <button className="button primary" disabled={saving}>{saving ? '创建中…' : '创建并继续'}</button>
    </form>
  </main>
}

