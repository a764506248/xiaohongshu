import { ChangeEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { contentApi } from '../api/content'
import { SERVER_BASE } from '../api/client'
import { Notice } from '../components/Notice'
import type { ImagePage, XiaohongshuPackage } from '../types'

function currentImage(page: ImagePage) {
  return page.versions.find(version => version.id === page.current_version_id) ?? page.versions.at(-1)
}

export function XiaohongshuPackagePage() {
  const { id = '' } = useParams()
  const [pkg, setPkg] = useState<XiaohongshuPackage | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [notCreated, setNotCreated] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [autoStarted, setAutoStarted] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await contentApi.getPackage(id)
      if (!data) {
        setPkg(null); setNotCreated(true); setSelectedId('')
        return
      }
      // 后端会先保存页面脚本，再并行生成图片；并行任务尚未结束或部分失败时，
      // current_version_id 为空。此时自动调用幂等的生成接口补齐缺失图片。
      if (data.pages.length === 0 || data.pages.some(page => !page.current_version_id)) {
        setPkg(null); setNotCreated(true); setSelectedId('')
        return
      }
      setPkg(data); setNotCreated(false); setSelectedId(current => current || data.pages[0]?.id || '')
    } catch (reason) {
      throw reason
    }
  }, [id])

  useEffect(() => { load().catch(reason => setError((reason as Error).message)) }, [load])
  useEffect(() => {
    if (!notCreated || autoStarted || busy) return
    setAutoStarted(true)
    setBusy('create')
    setError('')
    contentApi.createPackage(id)
      .then(data => {
        setPkg(data)
        setNotCreated(false)
        setSelectedId(data.pages[0]?.id || '')
        setSuccess('小红书平台内容与图片已生成')
      })
      .catch(reason => setError((reason as Error).message))
      .finally(() => setBusy(''))
  }, [autoStarted, busy, id, notCreated])
  const selected = useMemo(() => pkg?.pages.find(page => page.id === selectedId) ?? pkg?.pages[0], [pkg, selectedId])

  async function action(name: string, callback: () => Promise<unknown>, message = '') {
    setBusy(name); setError(''); setSuccess('')
    try { await callback(); await load(); if (message) setSuccess(message) }
    catch (reason) { setError((reason as Error).message) }
    finally { setBusy('') }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file || !selected) return
    await action('upload', () => contentApi.uploadImage(selected.id, file), '替换图片已保存')
    event.target.value = ''
  }

  async function move(direction: -1 | 1) {
    if (!pkg || !selected) return
    const ids = pkg.pages.map(page => page.id)
    const index = ids.indexOf(selected.id)
    const target = index + direction
    if (target < 0 || target >= ids.length) return
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    await action('order', () => contentApi.reorderPages(id, ids), '页面顺序已更新')
  }

  if (notCreated) return <main className="narrow"><Link className="back" to={`/tasks/${id}`}>← 返回文章</Link><section className="panel centered"><span className="step-number">04</span><h1>正在生成小红书平台内容</h1><p>独立平台 Graph 正在生成标题、正文、标签和 3～5 张竖版图片，图片会并行处理。</p>{error && <><Notice>{error}</Notice><button className="button primary" disabled={!!busy} onClick={() => { setAutoStarted(false); setError('') }}>重新生成</button></>} {!error && <button className="button primary" disabled>正在并行生成图片…</button>}</section></main>
  if (!pkg || !selected) return <main><div className="empty">正在加载内容包…</div>{error && <Notice>{error}</Notice>}</main>

  const image = currentImage(selected)
  return <main className="package-page">
    <Link className="back" to={`/tasks/${id}`}>← 返回文章</Link>
    <div className="page-heading"><div><p className="eyebrow">XIAOHONGSHU PACKAGE</p><h1>小红书内容包</h1><p>{pkg.pages.length} 张图片 · {pkg.validation_message}</p></div><a className="button primary" href={contentApi.exportUrl(id)}>导出 ZIP</a></div>
    {error && <Notice>{error}</Notice>}{success && <Notice type="success">{success}</Notice>}
    <section className="package-workspace">
      <div className="image-stage">
        {image && <img src={`${SERVER_BASE}${image.public_url}?v=${image.file_hash}`} alt={selected.title} />}
        <div className="page-tools"><button onClick={() => move(-1)} disabled={selected.page_number === 1 || !!busy}>← 前移</button><span>{selected.page_number} / {pkg.pages.length}</span><button onClick={() => move(1)} disabled={selected.page_number === pkg.pages.length || !!busy}>后移 →</button></div>
      </div>
      <aside className="package-controls panel">
        <h2>编辑当前图片</h2>
        <label>页面标题<input value={selected.title} onChange={event => setPkg({...pkg, pages: pkg.pages.map(page => page.id === selected.id ? {...page, title: event.target.value} : page)})} /></label>
        <label>页面正文<textarea rows={6} value={selected.body} onChange={event => setPkg({...pkg, pages: pkg.pages.map(page => page.id === selected.id ? {...page, body: event.target.value} : page)})} /></label>
        <label>视觉模板<select value={selected.template} onChange={event => setPkg({...pkg, pages: pkg.pages.map(page => page.id === selected.id ? {...page, template: event.target.value as ImagePage['template']} : page)})}><option value="editorial">编辑部浅色</option><option value="dark">深色技术感</option><option value="warm">温暖教育风</option></select></label>
        <button className="button primary" disabled={!!busy} onClick={() => action('page', () => contentApi.updateImagePage(selected.id, { title: selected.title, body: selected.body, template: selected.template }), '文字与图片已更新')}>保存并重新排版</button>
        <button className="button secondary" disabled={!!busy} onClick={() => action('regen', () => contentApi.regenerateImage(selected.id), '图片已重新生成')}>重新生成当前图片</button>
        <label className="button secondary upload-button">上传图片替换<input type="file" accept="image/png,image/jpeg,image/webp" onChange={upload} hidden /></label>
        <p className="version-note">当前版本 v{image?.version_number} · {image?.source_type}</p>
      </aside>
    </section>
    <div className="thumbnail-strip">{pkg.pages.map(page => { const thumb = currentImage(page); return <button className={page.id === selected.id ? 'active' : ''} key={page.id} onClick={() => setSelectedId(page.id)}>{thumb && <img src={`${SERVER_BASE}${thumb.public_url}?v=${thumb.file_hash}`} alt="" />}<span>{page.page_number}. {page.title}</span></button> })}</div>
    <section className="channel-editor panel"><div className="section-heading"><div><span className="step-number">05</span><h2>发布文案</h2></div><button className="button secondary" onClick={() => navigator.clipboard.writeText(`${pkg.title}\n\n${pkg.body}\n\n${pkg.tags}`).then(() => setSuccess('文案已复制'))}>复制全文</button></div>
      <label>标题<input value={pkg.title} onChange={event => setPkg({...pkg, title: event.target.value})} /></label><label>正文<textarea rows={12} value={pkg.body} onChange={event => setPkg({...pkg, body: event.target.value})} /></label><label>话题标签<input value={pkg.tags} onChange={event => setPkg({...pkg, tags: event.target.value})} /></label>
      <button className="button primary" disabled={!!busy} onClick={() => action('package', () => contentApi.updatePackage(id, {title: pkg.title, body: pkg.body, tags: pkg.tags}), '发布文案已保存')}>保存发布文案</button>
    </section>
  </main>
}
