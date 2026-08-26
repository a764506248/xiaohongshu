import {
  KeyOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
} from "antd";
import { useEffect, useState } from "react";
import type { AuthUser } from "../auth";
import { PermissionItem, userApi } from "../api/users";

export function UserManagementPage() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [permissions, setPermissions] = useState<PermissionItem[]>([]);
  const [editing, setEditing] = useState<AuthUser | null | undefined>();
  const [resetUser, setResetUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState("");
  const [form] = Form.useForm();
  const [passwordForm] = Form.useForm();
  const load = async () => {
    try {
      const [nextUsers, nextPermissions] = await Promise.all([
        userApi.list(),
        userApi.permissions(),
      ]);
      setUsers(nextUsers);
      setPermissions(nextPermissions);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  function openCreate() {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      role: "operator",
      status: "active",
      permission_codes: ["content:view"],
    });
  }
  function openEdit(user: AuthUser) {
    setEditing(user);
    form.setFieldsValue({ ...user });
  }
  async function save() {
    const values = await form.validateFields();
    try {
      if (editing) await userApi.update(editing.id, values);
      else await userApi.create(values);
      setEditing(undefined);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function resetPassword() {
    const values = await passwordForm.validateFields();
    if (resetUser) {
      await userApi.resetPassword(resetUser.id, values.password);
      setResetUser(null);
      passwordForm.resetFields();
    }
  }
  return (
    <main>
      <div className="page-heading">
        <div>
          <p className="eyebrow">USER & RBAC</p>
          <h1>用户与权限管理</h1>
          <p>创建后台用户并控制内容、发布、数据和系统管理权限。</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增用户
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
      <Card>
        <Table<AuthUser>
          rowKey="id"
          dataSource={users}
          pagination={false}
          columns={[
            {
              title: "用户",
              render: (_, u) => (
                <div className="user-cell">
                  <b>{u.display_name}</b>
                  <small>@{u.username}</small>
                </div>
              ),
            },
            {
              title: "角色",
              dataIndex: "role",
              render: (v) => (
                <Tag color={v === "admin" ? "red" : "blue"}>
                  {v === "admin" ? "管理员" : "运营人员"}
                </Tag>
              ),
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (v) => (
                <Tag color={v === "active" ? "success" : "default"}>
                  {v === "active" ? "正常" : "已停用"}
                </Tag>
              ),
            },
            {
              title: "权限",
              dataIndex: "permission_codes",
              render: (codes: string[], u) => (
                <Space wrap>
                  {u.role === "admin" ? (
                    <Tag icon={<SafetyCertificateOutlined />} color="red">
                      全部权限
                    </Tag>
                  ) : (
                    codes.map((code) => (
                      <Tag key={code}>
                        {permissions.find((p) => p.code === code)?.name || code}
                      </Tag>
                    ))
                  )}
                </Space>
              ),
            },
            {
              title: "最近登录",
              dataIndex: "last_login_at",
              render: (v) =>
                v ? new Date(v).toLocaleString("zh-CN") : "从未登录",
            },
            {
              title: "操作",
              width: 190,
              render: (_, u) => (
                <Space>
                  <Button size="small" onClick={() => openEdit(u)}>
                    编辑权限
                  </Button>
                  <Button
                    size="small"
                    icon={<KeyOutlined />}
                    onClick={() => setResetUser(u)}
                  >
                    重置密码
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Modal
        title={editing ? "编辑用户与权限" : "新增用户"}
        open={editing !== undefined}
        onCancel={() => setEditing(undefined)}
        onOk={save}
        okText="保存"
      >
        <Form form={form} layout="vertical" className="user-form">
          {!editing && (
            <>
              <Form.Item
                name="username"
                label="登录用户名"
                rules={[{ required: true }, { min: 3 }]}
              >
                <Input />
              </Form.Item>
              <Form.Item
                name="password"
                label="初始密码"
                rules={[{ required: true }, { min: 6 }]}
              >
                <Input.Password />
              </Form.Item>
            </>
          )}
          <Form.Item
            name="display_name"
            label="显示名称"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="role" label="用户角色" rules={[{ required: true }]}>
            <Select
              options={[
                { label: "管理员（拥有全部权限）", value: "admin" },
                { label: "运营人员", value: "operator" },
              ]}
            />
          </Form.Item>
          {editing && (
            <Form.Item name="status" label="账号状态">
              <Select
                options={[
                  { label: "正常", value: "active" },
                  { label: "停用", value: "disabled" },
                ]}
              />
            </Form.Item>
          )}
          <Form.Item
            noStyle
            shouldUpdate={(prev, next) => prev.role !== next.role}
          >
            {({ getFieldValue }) =>
              getFieldValue("role") !== "admin" && (
                <Form.Item name="permission_codes" label="分配权限">
                  <Checkbox.Group
                    className="permission-grid"
                    options={permissions.map((p) => ({
                      label: (
                        <span>
                          <b>{p.name}</b>
                          <small>{p.code}</small>
                        </span>
                      ),
                      value: p.code,
                    }))}
                  />
                </Form.Item>
              )
            }
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title={`重置 ${resetUser?.display_name || ""} 的密码`}
        open={!!resetUser}
        onCancel={() => setResetUser(null)}
        onOk={resetPassword}
      >
        <Form form={passwordForm} layout="vertical">
          <Form.Item
            name="password"
            label="新密码"
            rules={[{ required: true }, { min: 6, message: "密码至少 6 位" }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </main>
  );
}
