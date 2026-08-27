import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { contentApi } from '../api/content'
import { Notice } from '../components/Notice'
import { modelApi, type ModelConfiguration } from '../api/models'

export function TaskCreate() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [requirement, setRequirement] = useState('')
  const [audience, setAudience] = useState('AI 应用开发初学者')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [models, setModels] = useState<ModelConfiguration[]>([])
  const [modelId, setModelId] = useState('')

  useEffect(() => {
    modelApi.list().then(items => {
      const available = items.filter(item => item.enabled && item.capability === 'text' && ['openai_compatible', 'anthropic_compatible'].includes(item.protocol))
      setModels(available)
      setModelId(available.find(item => item.is_default)?.id ?? available[0]?.id ?? '')
    }).catch(e => setError(e.message))
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError('')
    try {
      const task = await contentApi.createTask({ title, requirement, target_audience: audience, model_configuration_id: modelId || null })
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
      <label>调用模型
        <select value={modelId} onChange={e => setModelId(e.target.value)}>
          <option value="">系统默认模型（ENV）</option>
          {models.map(model => <option value={model.id} key={model.id}>{model.name} · {model.model}</option>)}
        </select>
        <small>任务创建后，选题、文章生成和退回重写都会使用该模型。</small>
      </label>
      <label>补充要求<textarea rows={6} value={requirement} onChange={e => setRequirement(e.target.value)} placeholder="希望突出哪些观点、语气或案例？" /></label>
      <button className="button primary" disabled={saving}>{saving ? '创建中…' : '创建并继续'}</button>
    </form>
  </main>
}
