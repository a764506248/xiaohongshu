import { NavLink, Route, Routes } from 'react-router-dom'
import { TaskCreate } from './pages/TaskCreate'
import { TaskDetail } from './pages/TaskDetail'
import { TaskList } from './pages/TaskList'
import { XiaohongshuPackagePage } from './pages/XiaohongshuPackagePage'
import { ChannelsPage } from './pages/ChannelsPage'
import { PublishingPage } from './pages/PublishingPage'
import { AnalyticsPage } from './pages/AnalyticsPage'

export default function App() {
  return <div className="app-shell">
    <header className="topbar"><NavLink className="brand" to="/"><span>AI</span> 内容运营台</NavLink><nav><NavLink to="/">内容任务</NavLink><NavLink to="/publishing">发布排期</NavLink><NavLink to="/analytics">数据运营</NavLink></nav></header>
    <Routes><Route path="/" element={<TaskList />} /><Route path="/tasks/new" element={<TaskCreate />} /><Route path="/tasks/:id" element={<TaskDetail />} /><Route path="/tasks/:id/package" element={<XiaohongshuPackagePage />} /><Route path="/tasks/:id/channels" element={<ChannelsPage />} /><Route path="/publishing" element={<PublishingPage />} /><Route path="/analytics" element={<AnalyticsPage />} /></Routes>
  </div>
}
