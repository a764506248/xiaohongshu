import {
  CheckOutlined,
  CloseOutlined,
  CloudUploadOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { contentApi } from "../api/content";
import { useAuth } from "../auth";
import type { PublishJob } from "../types";

const statusMap: Record<string, { text: string; color: string }> = {
  pending_approval: { text: "待审批", color: "gold" },
  approved: { text: "待执行", color: "blue" },
  scheduled: { text: "已排期", color: "cyan" },
  awaiting_manual_publish: { text: "等待人工发布", color: "purple" },
  publishing: { text: "发布中", color: "processing" },
  published: { text: "已发布", color: "success" },
  failed: { text: "发布失败", color: "error" },
  rejected: { text: "已拒绝", color: "default" },
};
const channelMap: Record<string, string> = {
  xiaohongshu: "小红书",
  wechat: "微信公众号",
};

export function PublishingPage() {
  const { can } = useAuth();
  const [jobs, setJobs] = useState<PublishJob[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [manualJob, setManualJob] = useState<PublishJob | null>(null);
  const [metricJob, setMetricJob] = useState<PublishJob | null>(null);
  const [manualForm] = Form.useForm();
  const [metricForm] = Form.useForm();
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setJobs(await contentApi.listPublishJobs());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const filtered = useMemo(
    () =>
      filter === "all"
        ? jobs
        : jobs.filter((job) =>
            filter === "pending"
              ? job.approval_status === "pending"
              : job.status === filter,
          ),
    [jobs, filter],
  );
  const counts = {
    pending: jobs.filter((j) => j.approval_status === "pending").length,
    manual: jobs.filter((j) => j.status === "awaiting_manual_publish").length,
    published: jobs.filter((j) => j.status === "published").length,
    failed: jobs.filter((j) => j.status === "failed").length,
  };
  async function act(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function completeManual() {
    const values = await manualForm.validateFields();
    if (manualJob)
      await act(() =>
        contentApi.completeManual(manualJob.id, values.external_post_id),
      );
    setManualJob(null);
    manualForm.resetFields();
  }
  async function saveMetric() {
    const values = await metricForm.validateFields();
    if (metricJob) await act(() => contentApi.addMetric(metricJob.id, values));
    setMetricJob(null);
    metricForm.resetFields();
  }
  return (
    <main>
      <div className="page-heading">
        <div>
          <p className="eyebrow">PUBLISH MANAGEMENT</p>
          <h1>发布管理</h1>
          <p>统一处理内容审批、平台发布、失败重试和效果数据回收。</p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load}>
          刷新
        </Button>
      </div>
      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          onClose={() => setError("")}
        />
      )}
      <div className="publish-stat-grid">
        <Card>
          <Statistic title="待审批" value={counts.pending} />
        </Card>
        <Card>
          <Statistic title="等待人工发布" value={counts.manual} />
        </Card>
        <Card>
          <Statistic title="已发布" value={counts.published} />
        </Card>
        <Card>
          <Statistic
            title="失败任务"
            value={counts.failed}
            valueStyle={counts.failed ? { color: "#cf1322" } : undefined}
          />
        </Card>
      </div>
      <Card
        className="publish-table-card"
        title="发布任务"
        extra={
          <Segmented
            value={filter}
            onChange={(v) => setFilter(String(v))}
            options={[
              { label: "全部", value: "all" },
              { label: "待审批", value: "pending" },
              { label: "人工发布", value: "awaiting_manual_publish" },
              { label: "已发布", value: "published" },
              { label: "失败", value: "failed" },
            ]}
          />
        }
      >
        <Table<PublishJob>
          rowKey="id"
          loading={loading}
          dataSource={filtered}
          scroll={{ x: 1050 }}
          pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
          columns={[
            {
              title: "发布内容",
              dataIndex: "content_title",
              width: 260,
              ellipsis: true,
              render: (value, row) => (
                <div className="publish-content">
                  <b>{value || "未命名内容"}</b>
                  <small>
                    {channelMap[row.channel || ""] || row.channel || "未知平台"}{" "}
                    · {row.account_name || "未知账号"}
                  </small>
                </div>
              ),
            },
            {
              title: "发布方式",
              dataIndex: "account_mode",
              width: 100,
              render: (value) => (
                <Tag color={value === "xhs_mcp" ? "red" : undefined}>
                  {value === "manual"
                    ? "人工"
                    : value === "xhs_mcp"
                      ? "XHS MCP"
                      : "模拟自动"}
                </Tag>
              ),
            },
            {
              title: "状态",
              dataIndex: "status",
              width: 130,
              render: (value) => {
                const status = statusMap[value] || {
                  text: value,
                  color: "default",
                };
                return <Tag color={status.color}>{status.text}</Tag>;
              },
            },
            {
              title: "发布时间",
              width: 180,
              render: (_, row) =>
                row.published_at
                  ? new Date(row.published_at).toLocaleString("zh-CN")
                  : row.scheduled_at
                    ? new Date(row.scheduled_at).toLocaleString("zh-CN")
                    : "审批后立即处理",
            },
            {
              title: "重试",
              width: 80,
              render: (_, row) => `${row.retry_count}/${row.max_retries}`,
            },
            {
              title: "平台结果",
              dataIndex: "external_post_id",
              ellipsis: true,
              render: (value) =>
                value ? (
                  <Tooltip title={value}>
                    {/^https?:\/\//.test(value) ? (
                      <a href={value} target="_blank" rel="noreferrer">
                        查看笔记
                      </a>
                    ) : (
                      <span>{value}</span>
                    )}
                  </Tooltip>
                ) : (
                  "—"
                ),
            },
            {
              title: "操作",
              fixed: "right",
              width: 250,
              render: (_, row) => (
                <Space wrap>
                  {can("publish:approve") && row.approval_status === "pending" && (
                    <>
                      <Button
                        type="primary"
                        size="small"
                        icon={<CheckOutlined />}
                        onClick={() =>
                          act(() =>
                            contentApi.decidePublishJob(row.id, "approve"),
                          )
                        }
                      >
                        批准
                      </Button>
                      <Button
                        size="small"
                        danger
                        icon={<CloseOutlined />}
                        onClick={() =>
                          act(() =>
                            contentApi.decidePublishJob(
                              row.id,
                              "reject",
                              "运营人员拒绝",
                            ),
                          )
                        }
                      >
                        拒绝
                      </Button>
                    </>
                  )}
                  {can("publish:execute") && row.status === "approved" && (
                    <Button
                      type="primary"
                      size="small"
                      onClick={() =>
                        act(() => contentApi.executePublishJob(row.id))
                      }
                    >
                      执行
                    </Button>
                  )}
                  {can("publish:execute") && row.status === "awaiting_manual_publish" && (
                    <Button
                      type="primary"
                      size="small"
                      icon={<CloudUploadOutlined />}
                      onClick={() => setManualJob(row)}
                    >
                      确认发布
                    </Button>
                  )}
                  {can("publish:execute") && row.status === "failed" && (
                    <Button
                      size="small"
                      danger
                      onClick={() =>
                        act(() => contentApi.retryPublishJob(row.id))
                      }
                    >
                      重试
                    </Button>
                  )}
                  {can("publish:metrics") && row.status === "published" && (
                    <>
                      {row.channel === "xiaohongshu" && row.account_mode === "xhs_mcp" && (
                        <Button size="small" onClick={() => act(() => contentApi.syncMetric(row.id))}>
                          同步数据
                        </Button>
                      )}
                      <Button size="small" onClick={() => setMetricJob(row)}>
                        手工录入
                      </Button>
                    </>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Modal
        title="确认人工发布完成"
        open={!!manualJob}
        onCancel={() => setManualJob(null)}
        onOk={completeManual}
        okText="确认完成"
      >
        <Alert
          type="info"
          showIcon
          message="请先在平台完成发布，再填写平台内容 ID 或内容链接。"
        />
        <Form
          form={manualForm}
          layout="vertical"
          className="publish-modal-form"
        >
          <Form.Item
            label="平台内容 ID 或 URL"
            name="external_post_id"
            rules={[{ required: true, message: "请填写发布结果" }]}
          >
            <Input placeholder="例如：https://平台内容地址" />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="录入内容效果数据"
        open={!!metricJob}
        onCancel={() => setMetricJob(null)}
        onOk={saveMetric}
        okText="保存数据"
      >
        <Form
          form={metricForm}
          layout="vertical"
          className="metric-form"
          initialValues={{
            views: 0,
            likes: 0,
            favorites: 0,
            comments: 0,
            shares: 0,
            follower_gain: 0,
          }}
        >
          {[
            ["views", "阅读/曝光"],
            ["likes", "点赞"],
            ["favorites", "收藏"],
            ["comments", "评论"],
            ["shares", "分享"],
            ["follower_gain", "粉丝增长"],
          ].map(([name, label]) => (
            <Form.Item
              key={name}
              name={name}
              label={label}
              rules={[{ required: true }]}
            >
              <InputNumber
                min={name === "follower_gain" ? undefined : 0}
                precision={0}
              />
            </Form.Item>
          ))}
        </Form>
      </Modal>
    </main>
  );
}
