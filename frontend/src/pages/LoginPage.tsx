import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />

  async function submit(values: { username: string; password: string }) {
    setBusy(true); setError('')
    try {
      await login(values.username, values.password)
      navigate((location.state as { from?: string })?.from || '/', { replace: true })
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="login-page">
    <div className="login-brand"><span>AI</span><div><b>内容运营管理系统</b><small>CONTENT OPERATIONS ADMIN</small></div></div>
    <Card className="login-card" variant="borderless">
      <Typography.Title level={2}>欢迎登录</Typography.Title>
      <Typography.Paragraph type="secondary">登录后台，继续管理内容生产与发布流程</Typography.Paragraph>
      {error && <Alert type="error" message={error} showIcon />}
      <Form layout="vertical" size="large" onFinish={submit} initialValues={{ username: 'admin' }}>
        <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}><Input prefix={<UserOutlined />} placeholder="请输入用户名" /></Form.Item>
        <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}><Input.Password prefix={<LockOutlined />} placeholder="请输入密码" /></Form.Item>
        <Button type="primary" htmlType="submit" loading={busy} block>登录系统</Button>
      </Form>
      <p className="login-hint">本地默认账号：admin / admin123</p>
    </Card>
    <footer>AI 内容运营系统 · 内部管理平台</footer>
  </div>
}
