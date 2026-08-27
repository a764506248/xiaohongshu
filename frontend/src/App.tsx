import {
  BarChartOutlined,
  CalendarOutlined,
  FileTextOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  SnippetsOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import {
  Avatar,
  Button,
  ConfigProvider,
  Drawer,
  Dropdown,
  Grid,
  Layout,
  Menu,
  Spin,
  theme,
} from "antd";
import { useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useAuth } from "./auth";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ChannelsPage } from "./pages/ChannelsPage";
import { LoginPage } from "./pages/LoginPage";
import { ModelManagementPage } from "./pages/ModelManagementPage";
import { PromptManagementPage } from "./pages/PromptManagementPage";
import { PublishingPage } from "./pages/PublishingPage";
import { TaskCreate } from "./pages/TaskCreate";
import { TaskDetail } from "./pages/TaskDetail";
import { TaskList } from "./pages/TaskList";
import { UserManagementPage } from "./pages/UserManagementPage";
import { XiaohongshuPackagePage } from "./pages/XiaohongshuPackagePage";
const { Header, Sider, Content } = Layout;
function AdminLayout() {
  const { user, logout, can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const screens = Grid.useBreakpoint();
  const mobile = screens.md === false;
  const selected = location.pathname.startsWith("/publishing")
    ? "/publishing"
    : location.pathname.startsWith("/analytics")
      ? "/analytics"
      : location.pathname.startsWith("/users")
        ? "/users"
        : location.pathname.startsWith("/models")
          ? "/models"
          : location.pathname.startsWith("/prompts")
            ? "/prompts"
            : "/";
  const menuItems = [
    {
      key: "/",
      icon: <FileTextOutlined />,
      label: "内容任务",
      show: can("content:view"),
    },
    {
      key: "/publishing",
      icon: <CalendarOutlined />,
      label: "发布管理",
      show: can("publish:view"),
    },
    {
      key: "/analytics",
      icon: <BarChartOutlined />,
      label: "数据运营",
      show: can("analytics:view"),
    },
    {
      key: "/users",
      icon: <TeamOutlined />,
      label: "用户与权限",
      show: can("users:manage"),
    },
    {
      key: "/models",
      icon: <RobotOutlined />,
      label: "模型管理",
      show: true,
    },
    {
      key: "/prompts",
      icon: <SnippetsOutlined />,
      label: "Prompt 管理",
      show: true,
    },
  ].filter((item) => item.show);
  return (
    <Layout className="admin-layout">
      <Sider
        collapsible
        collapsed={collapsed}
        trigger={null}
        width={196}
        collapsedWidth={68}
        className="admin-sider"
      >
        <div className="admin-logo">
          <span>AI</span>
          {!collapsed && (
            <div>
              <b>内容运营</b>
              <small>ADMIN SYSTEM</small>
            </div>
          )}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
        <div className="sider-version">{collapsed ? "V1" : "VERSION 1.0"}</div>
      </Sider>
      <Drawer
        title="内容运营"
        placement="left"
        width={260}
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        className="mobile-navigation"
      >
        <Menu
          mode="inline"
          selectedKeys={[selected]}
          items={menuItems}
          onClick={({ key }) => {
            navigate(key);
            setMobileMenuOpen(false);
          }}
        />
      </Drawer>
      <Layout>
        <Header className="admin-header">
          <Button
            type="text"
            icon={mobile || collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => mobile ? setMobileMenuOpen(true) : setCollapsed(!collapsed)}
          />
          <div className="header-right">
            <span className="environment-dot">本地环境</span>
            <Dropdown
              menu={{
                items: [
                  {
                    key: "logout",
                    icon: <LogoutOutlined />,
                    label: "退出登录",
                    onClick: logout,
                  },
                ],
              }}
            >
              <div className="user-menu">
                <Avatar icon={<UserOutlined />} />
                <div>
                  <b>{user?.display_name}</b>
                  <small>
                    {user?.role === "admin" ? "系统管理员" : "运营人员"}
                  </small>
                </div>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content className="admin-content">
          <div className="content-surface">
            <Routes>
              <Route path="/" element={<TaskList />} />
              <Route path="/tasks/new" element={<TaskCreate />} />
              <Route path="/tasks/:id" element={<TaskDetail />} />
              <Route
                path="/tasks/:id/package"
                element={<XiaohongshuPackagePage />}
              />
              <Route path="/tasks/:id/channels" element={<ChannelsPage />} />
              <Route
                path="/publishing"
                element={
                  can("publish:view") ? (
                    <PublishingPage />
                  ) : (
                    <Navigate to="/" replace />
                  )
                }
              />
              <Route
                path="/analytics"
                element={
                  can("analytics:view") ? (
                    <AnalyticsPage />
                  ) : (
                    <Navigate to="/" replace />
                  )
                }
              />
              <Route
                path="/users"
                element={
                  can("users:manage") ? (
                    <UserManagementPage />
                  ) : (
                    <Navigate to="/" replace />
                  )
                }
              />
              <Route path="/models" element={<ModelManagementPage />} />
              <Route path="/prompts" element={<PromptManagementPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
function ProtectedApp() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <div className="app-loading">
        <Spin size="large" />
      </div>
    );
  if (!user)
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <AdminLayout />;
}
export default function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: "#ef4f3c",
          borderRadius: 8,
          fontFamily: "'Inter','Noto Sans SC',sans-serif",
          colorBgLayout: "#f4f6f8",
        },
      }}
    >
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={<ProtectedApp />} />
      </Routes>
    </ConfigProvider>
  );
}
