import {
  CheckCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  PlusOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Form,
  Image,
  Input,
  message,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import { useEffect, useState } from "react";
import {
  modelApi,
  type ModelConfiguration,
  type ModelTestResult,
} from "../api/models";
import { useAuth } from "../auth";

type ModelForm = {
  name: string;
  provider: string;
  model: string;
  capability: string;
  protocol: string;
  base_url: string;
  api_key?: string;
  enabled: boolean;
};

export function ModelManagementPage() {
  const { user } = useAuth();
  const [form] = Form.useForm<ModelForm>();
  const [models, setModels] = useState<ModelConfiguration[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState("");
  const [result, setResult] = useState<ModelTestResult | null>(null);
  const [editing, setEditing] = useState<ModelConfiguration | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const load = () =>
    modelApi
      .list()
      .then(setModels)
      .catch((e: Error) => message.error(e.message))
      .finally(() => setLoading(false));
  useEffect(() => {
    void load();
  }, []);
  const canWrite = (row: ModelConfiguration) =>
    user?.role === "admin" || !row.is_system;
  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      provider: "openrouter",
      capability: "text",
      protocol: "openai_compatible",
      base_url: "https://openrouter.ai/api/v1",
      enabled: true,
    });
    setFormOpen(true);
  };
  const openEdit = (row: ModelConfiguration) => {
    setEditing(row);
    form.setFieldsValue({ ...row, api_key: undefined });
    setFormOpen(true);
  };
  const save = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing)
        await modelApi.edit(editing.id, {
          ...values,
          is_default: editing.is_default,
        });
      else await modelApi.create(values);
      message.success(editing ? "模型已更新" : "模型已添加");
      setFormOpen(false);
      await load();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  const update = async (
    row: ModelConfiguration,
    enabled: boolean,
    isDefault = row.is_default,
  ) => {
    try {
      await modelApi.edit(row.id, { enabled, is_default: isDefault });
      await load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };
  const remove = (row: ModelConfiguration) =>
    Modal.confirm({
      title: "删除模型配置？",
      content: `将删除“${row.name}”及其 API Key，此操作不可恢复。`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        try {
          await modelApi.remove(row.id);
          message.success("模型已删除");
          await load();
        } catch (e) {
          message.error((e as Error).message);
        }
      },
    });
  const test = (row: ModelConfiguration) =>
    Modal.confirm({
      title: `测试 ${row.name}`,
      icon: <WarningOutlined />,
      content:
        row.capability === "image"
          ? "会发起一次真实图片生成调用，可能产生费用。"
          : row.capability === "text"
            ? "会发起一次真实文本调用，可能产生 Token 费用。"
            : "图生视频模型需要输入图片，当前页面暂不支持测试。",
      okText: "确认调用",
      cancelText: "取消",
      okButtonProps: { disabled: row.capability === "image_to_video" },
      onOk: async () => {
        setTesting(row.id);
        try {
          setResult(
            await modelApi.test(
              row.id,
              row.capability === "text"
                ? "请用一句中文回复：模型连接正常。"
                : "一张简洁专业的 AI 编程课程海报，红黑配色，竖版构图",
            ),
          );
          message.success("模型调用成功");
        } catch (e) {
          message.error((e as Error).message);
        } finally {
          setTesting("");
        }
      },
    });
  return (
    <main className="model-page">
      <div className="model-heading">
        <div>
          <h1>模型管理</h1>
          <Typography.Text type="secondary">
            系统模型与我添加的模型统一管理
          </Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          添加模型
        </Button>
      </div>
      <Alert
        showIcon
        type="warning"
        message="当前按你的要求暂时明文保存 API Key"
        description="接口不会返回密钥内容；正式上线前建议迁移为加密存储。"
      />
      <Table
        rowKey="id"
        loading={loading}
        dataSource={models}
        pagination={false}
        columns={[
          {
            title: "模型",
            render: (_, row) => (
              <div>
                <Space>
                  <b>{row.name}</b>
                  <Tag>{row.is_system ? "系统" : "我的"}</Tag>
                </Space>
                <small>{row.model}</small>
              </div>
            ),
          },
          { title: "供应商", dataIndex: "provider", width: 150 },
          {
            title: "能力",
            width: 110,
            render: (_, row) => (
              <Tag
                color={
                  row.capability === "image"
                    ? "blue"
                    : row.capability === "text"
                      ? "green"
                      : "purple"
                }
              >
                {row.capability === "image"
                  ? "图片生成"
                  : row.capability === "text"
                    ? "文本生成"
                    : "图生视频"}
              </Tag>
            ),
          },
          {
            title: "密钥",
            width: 90,
            render: (_, row) => (
              <Tag color={row.has_api_key ? "success" : "default"}>
                {row.has_api_key ? "已配置" : "环境变量"}
              </Tag>
            ),
          },
          {
            title: "启用",
            width: 75,
            render: (_, row) => (
              <Switch
                checked={row.enabled}
                disabled={!canWrite(row)}
                onChange={(checked) =>
                  update(row, checked, checked ? row.is_default : false)
                }
              />
            ),
          },
          {
            title: "默认",
            width: 90,
            render: (_, row) =>
              row.is_default ? (
                <Tag icon={<CheckCircleOutlined />} color="success">
                  默认
                </Tag>
              ) : (
                <Button
                  type="link"
                  disabled={!row.enabled || !canWrite(row)}
                  onClick={() => update(row, true, true)}
                >
                  设为默认
                </Button>
              ),
          },
          {
            title: "操作",
            width: 190,
            render: (_, row) => (
              <Space>
                <Button
                  icon={<ExperimentOutlined />}
                  loading={testing === row.id}
                  disabled={!row.enabled}
                  onClick={() => test(row)}
                >
                  测试
                </Button>
                {canWrite(row) && (
                  <Button
                    icon={<EditOutlined />}
                    onClick={() => openEdit(row)}
                  />
                )}{" "}
                {!row.is_system && (
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => remove(row)}
                  />
                )}
              </Space>
            ),
          },
        ]}
      />
      <Modal
        open={formOpen}
        title={editing ? "编辑模型" : "添加模型"}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        onOk={save}
        onCancel={() => setFormOpen(false)}
        width={620}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="显示名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space align="start" style={{ display: "flex" }}>
            <Form.Item
              name="provider"
              label="供应商标识"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="openrouter" />
            </Form.Item>
            <Form.Item
              name="model"
              label="模型 ID"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="provider/model-name" />
            </Form.Item>
          </Space>
          <Space align="start" style={{ display: "flex" }}>
            <Form.Item
              name="capability"
              label="模型能力"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Select
                options={[
                  { value: "text", label: "文本生成" },
                  { value: "image", label: "图片生成" },
                  { value: "image_to_video", label: "图生视频" },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="protocol"
              label="接口协议"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Select
                options={[
                  { value: "openai_compatible", label: "OpenAI Compatible" },
                  { value: "dashscope_native", label: "DashScope Native" },
                  {
                    value: "anthropic_compatible",
                    label: "Anthropic Compatible",
                  },
                ]}
              />
            </Form.Item>
          </Space>
          <Form.Item
            name="base_url"
            label="Base URL"
            rules={[{ required: true }, { type: "url" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="api_key"
            label={editing ? "API Key（留空表示不修改）" : "API Key"}
            rules={editing ? [] : [{ required: true }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="enabled" label="立即启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        open={!!result}
        title="模型测试结果"
        footer={null}
        onCancel={() => setResult(null)}
      >
        {result && (
          <Space direction="vertical">
            <Typography.Text>
              模型：{result.model} · 耗时 {result.latency_ms} ms
            </Typography.Text>
            {result.output_url && <Image src={result.output_url} />}{" "}
            {result.output_text && (
              <Typography.Paragraph copyable>
                {result.output_text}
              </Typography.Paragraph>
            )}
          </Space>
        )}
      </Modal>
    </main>
  );
}
