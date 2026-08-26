import {
  DeleteOutlined,
  EditOutlined,
  HistoryOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import {
  Button,
  Form,
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
  promptApi,
  type PromptTemplate,
  type PromptVersion,
} from "../api/prompts";
import { useAuth } from "../auth";

type PromptForm = {
  name: string;
  prompt_key: string;
  tags: string[];
  scene: string;
  model_capability: string;
  description: string;
  system_prompt: string;
  user_prompt_template: string;
  variables: string[];
  change_note: string;
  status: string;
  is_default: boolean;
};
export function PromptManagementPage() {
  const { user } = useAuth();
  const [form] = Form.useForm<PromptForm>();
  const [rows, setRows] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<PromptTemplate | null>(null);
  const [saving, setSaving] = useState(false);
  const [history, setHistory] = useState<PromptVersion[]>([]);
  const [historyPrompt, setHistoryPrompt] = useState<PromptTemplate | null>(
    null,
  );
  const load = () =>
    promptApi
      .list()
      .then(setRows)
      .catch((e: Error) => message.error(e.message))
      .finally(() => setLoading(false));
  useEffect(() => {
    void load();
  }, []);
  const canWrite = (row: PromptTemplate) =>
    user?.role === "admin" || !row.is_system;
  const create = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      tags: [],
      variables: [],
      model_capability: "text",
      status: "enabled",
      is_default: false,
      change_note: "创建初始版本",
    });
    setOpen(true);
  };
  const edit = (row: PromptTemplate) => {
    setEditing(row);
    form.setFieldsValue({
      name: row.name,
      prompt_key: row.prompt_key,
      tags: row.tags,
      scene: row.scene,
      model_capability: row.model_capability,
      description: row.description,
      system_prompt: row.current_version?.system_prompt || "",
      user_prompt_template: row.current_version?.user_prompt_template || "",
      variables: JSON.parse(row.current_version?.variables_json || "[]"),
      change_note: "更新 Prompt",
      status: row.status,
      is_default: row.is_default,
    });
    setOpen(true);
  };
  const save = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      editing
        ? await promptApi.update(editing.id, values)
        : await promptApi.create(values);
      message.success(editing ? "已创建新版本" : "Prompt 已创建");
      setOpen(false);
      await load();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  const showHistory = async (row: PromptTemplate) => {
    try {
      setHistory(await promptApi.versions(row.id));
      setHistoryPrompt(row);
    } catch (e) {
      message.error((e as Error).message);
    }
  };
  const rollback = async (version: number) => {
    if (!historyPrompt) return;
    try {
      await promptApi.rollback(historyPrompt.id, version);
      message.success("已基于历史内容创建新版本");
      setHistoryPrompt(null);
      await load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };
  const remove = (row: PromptTemplate) =>
    Modal.confirm({
      title: "删除 Prompt？",
      content: `将同时删除“${row.name}”的全部版本。`,
      okType: "danger",
      okText: "删除",
      cancelText: "取消",
      onOk: async () => {
        await promptApi.remove(row.id);
        await load();
      },
    });
  return (
    <main className="prompt-page">
      <div className="prompt-heading">
        <div>
          <h1>Prompt 管理</h1>
          <Typography.Text type="secondary">
            使用稳定 Prompt Key 管理系统模板、个人模板与历史版本
          </Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={create}>
          添加 Prompt
        </Button>
      </div>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        pagination={{ pageSize: 15 }}
        columns={[
          {
            title: "名称",
            render: (_, r) => (
              <div>
                <Space>
                  <b>{r.name}</b>
                  <Tag>{r.is_system ? "系统" : "我的"}</Tag>
                  {r.is_default && <Tag color="success">默认</Tag>}
                </Space>
                <small>{r.prompt_key}</small>
              </div>
            ),
          },
          {
            title: "标签",
            render: (_, r) => (
              <Space wrap>
                {r.tags.map((t) => (
                  <Tag key={t}>{t}</Tag>
                ))}
              </Space>
            ),
          },
          { title: "场景", dataIndex: "scene", width: 150 },
          {
            title: "版本",
            width: 80,
            render: (_, r) => `v${r.current_version?.version_number || 0}`,
          },
          {
            title: "状态",
            width: 90,
            render: (_, r) => (
              <Tag color={r.status === "enabled" ? "success" : "default"}>
                {r.status}
              </Tag>
            ),
          },
          {
            title: "操作",
            width: 180,
            render: (_, r) => (
              <Space>
                <Button
                  icon={<HistoryOutlined />}
                  onClick={() => showHistory(r)}
                >
                  历史
                </Button>
                {canWrite(r) && (
                  <Button icon={<EditOutlined />} onClick={() => edit(r)} />
                )}{" "}
                {!r.is_system && (
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => remove(r)}
                  />
                )}
              </Space>
            ),
          },
        ]}
      />
      <Modal
        open={open}
        title={editing ? "编辑并创建新版本" : "添加 Prompt"}
        width={780}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        onOk={save}
        onCancel={() => setOpen(false)}
      >
        <Form form={form} layout="vertical">
          <Space align="start" style={{ display: "flex" }}>
            <Form.Item
              name="name"
              label="名称"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="prompt_key"
              label="Prompt Key"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Input
                disabled={!!editing}
                placeholder="content.generate_topics"
              />
            </Form.Item>
          </Space>
          <Space align="start" style={{ display: "flex" }}>
            <Form.Item
              name="scene"
              label="使用场景"
              rules={[{ required: true }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="topic_generation" />
            </Form.Item>
            <Form.Item
              name="model_capability"
              label="模型能力"
              style={{ flex: 1 }}
            >
              <Select
                options={[
                  { value: "text", label: "文本" },
                  { value: "image", label: "图片" },
                  { value: "image_to_video", label: "视频" },
                ]}
              />
            </Form.Item>
            <Form.Item name="status" label="状态" style={{ flex: 1 }}>
              <Select
                options={[
                  { value: "draft", label: "草稿" },
                  { value: "enabled", label: "启用" },
                  { value: "disabled", label: "停用" },
                ]}
              />
            </Form.Item>
          </Space>
          <Form.Item name="tags" label="标签">
            <Select
              mode="tags"
              tokenSeparators={[","]}
              placeholder="输入标签后回车"
            />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="system_prompt" label="System Prompt">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item
            name="user_prompt_template"
            label="User Prompt 模板"
            rules={[{ required: true }]}
            extra="变量使用双花括号，例如 {{ title }}"
          >
            <Input.TextArea rows={7} />
          </Form.Item>
          <Form.Item name="variables" label="模板变量">
            <Select
              mode="tags"
              tokenSeparators={[","]}
              placeholder="title、audience、instruction"
            />
          </Form.Item>
          <Space>
            <Form.Item
              name="is_default"
              label="设为该 Key 的默认版本"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item name="change_note" label="版本说明">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        open={!!historyPrompt}
        title={`${historyPrompt?.name || ""} · 版本历史`}
        footer={null}
        width={720}
        onCancel={() => setHistoryPrompt(null)}
      >
        <Table
          rowKey="id"
          dataSource={history}
          pagination={false}
          columns={[
            {
              title: "版本",
              dataIndex: "version_number",
              width: 80,
              render: (v) => `v${v}`,
            },
            { title: "说明", dataIndex: "change_note" },
            {
              title: "时间",
              dataIndex: "created_at",
              render: (v) => new Date(v).toLocaleString("zh-CN"),
            },
            {
              title: "操作",
              width: 90,
              render: (_, v) => (
                <Button
                  disabled={!canWrite(historyPrompt!)}
                  onClick={() => rollback(v.version_number)}
                >
                  回滚
                </Button>
              ),
            },
          ]}
        />
      </Modal>
    </main>
  );
}
