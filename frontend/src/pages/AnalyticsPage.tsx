import { ApiOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { Card, Col, DatePicker, Empty, Row, Segmented, Statistic, Table, Tag } from 'antd'
import dayjs, { Dayjs } from 'dayjs'
import { useEffect, useMemo, useState } from 'react'
import { contentApi } from '../api/content'
import type { AnalyticsSummary, ContentMetric, ModelUsage, TokenUsageReport } from '../types'

const { RangePicker } = DatePicker
const number = new Intl.NumberFormat('zh-CN')
type Granularity = 'day' | 'month' | 'year'

export function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [usage, setUsage] = useState<ModelUsage[]>([])
  const [metrics, setMetrics] = useState<ContentMetric[]>([])
  const [granularity, setGranularity] = useState<Granularity>('day')
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')])
  const [report, setReport] = useState<TokenUsageReport | null>(null)
  const [reportLoading, setReportLoading] = useState(false)

  useEffect(() => {
    contentApi.analytics().then(setSummary)
    contentApi.modelUsage().then(setUsage)
    contentApi.contentMetrics().then(setMetrics)
  }, [])
  useEffect(() => {
    setReportLoading(true)
    contentApi.tokenUsage(range[0].toISOString(), range[1].toISOString(), granularity).then(setReport).finally(() => setReportLoading(false))
  }, [range, granularity])

  const averageLatency = useMemo(() => summary?.model_calls ? Math.round(summary.total_latency_ms / summary.model_calls) : 0, [summary])
  const maxPoint = Math.max(...(report?.points.map(point => point.total_tokens) ?? [0]), 1)
  if (!summary) return <main><div className="empty">加载运营数据…</div></main>

  return <main>
    <div className="page-heading"><div><p className="eyebrow">ANALYTICS</p><h1>数据运营与模型消耗</h1><p>分析已发布文章效果，并查看模型 Token 消耗。</p></div></div>
    <Row gutter={[16, 16]} className="token-statistics">
      <Col xs={24} sm={12} xl={6}><Card><Statistic title="已发布文章" value={summary.published_posts} /></Card></Col>
      <Col xs={24} sm={12} xl={6}><Card><Statistic title="累计浏览" value={summary.total_views} /></Card></Col>
      <Col xs={24} sm={12} xl={6}><Card><Statistic title="累计互动" value={summary.total_interactions} /></Card></Col>
      <Col xs={24} sm={12} xl={6}><Card><Statistic title="累计 Token" value={summary.total_tokens} formatter={value => number.format(Number(value))} prefix={<ApiOutlined />} /></Card></Col>
    </Row>
    <Card title={`文章效果快照（${metrics.length} 条）`} className="usage-table-card">
      <Table<ContentMetric> rowKey="id" dataSource={metrics} scroll={{ x: 1050 }} pagination={{ pageSize: 10 }} locale={{ emptyText: <Empty description="请到发布管理同步文章数据" /> }} columns={[
        { title: '采集时间', dataIndex: 'collected_at', width: 180, render: value => new Date(value).toLocaleString('zh-CN') },
        { title: '文章', dataIndex: 'content_title', ellipsis: true, render: (value, row) => row.external_post_id ? <a href={row.external_post_id} target="_blank" rel="noreferrer">{value}</a> : value },
        { title: '平台', dataIndex: 'channel', width: 90, render: value => <Tag>{value === 'xiaohongshu' ? '小红书' : value}</Tag> },
        ...['views', 'likes', 'favorites', 'comments', 'shares'].map((key, index) => ({ title: ['浏览', '点赞', '收藏', '评论', '分享'][index], dataIndex: key, align: 'right' as const, render: (value: number) => number.format(value) })),
        { title: '表现分', dataIndex: 'performance_score', align: 'right', render: value => <b>{value}</b> },
      ]} />
    </Card>
    <Card className="trend-card" loading={reportLoading} title="Token 时间趋势" extra={<div className="report-filters"><Segmented value={granularity} options={[{ label: '日统计', value: 'day' }, { label: '月统计', value: 'month' }, { label: '年统计', value: 'year' }]} onChange={value => setGranularity(value as Granularity)} /><RangePicker value={range} allowClear={false} onChange={value => value && setRange(value as [Dayjs, Dayjs])} /></div>}>
      <div className="range-summary"><span>调用 <b>{report?.calls ?? 0}</b> 次</span><span>输入 <b>{number.format(report?.input_tokens ?? 0)}</b></span><span>输出 <b>{number.format(report?.output_tokens ?? 0)}</b></span><span>总计 <b>{number.format(report?.total_tokens ?? 0)} Token</b></span></div>
      {!report?.points.length ? <Empty description="所选时间范围内暂无模型调用" /> : <div className="token-chart">{report.points.map(point => <div className="chart-row" key={point.period}><span>{point.period}</span><div className="chart-track"><i style={{ width: `${Math.max(point.total_tokens / maxPoint * 100, 2)}%` }} /></div><b>{number.format(point.total_tokens)}</b><small>{point.calls} 次</small></div>)}</div>}
    </Card>
    <Card title={`模型调用明细（最近 ${usage.length} 条）`} className="usage-table-card"><Table<ModelUsage> rowKey="id" dataSource={usage} pagination={{ pageSize: 10 }} columns={[
      { title: '调用时间', dataIndex: 'created_at', render: value => new Date(value).toLocaleString('zh-CN') },
      { title: '场景', dataIndex: 'operation' }, { title: '模型', dataIndex: 'model', ellipsis: true },
      { title: '输入', dataIndex: 'input_tokens', align: 'right' }, { title: '输出', dataIndex: 'output_tokens', align: 'right' },
      { title: '耗时', dataIndex: 'latency_ms', align: 'right', render: value => <span><ClockCircleOutlined /> {value} ms</span> },
      { title: '状态', dataIndex: 'status', render: value => <Tag color={value === 'success' ? 'success' : 'error'}>{value}</Tag> },
    ]} /></Card>
  </main>
}
