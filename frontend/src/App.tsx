import { NavLink, Route, Routes } from 'react-router-dom'
import { TaskCreate } from './pages/TaskCreate'
import { TaskDetail } from './pages/TaskDetail'
import { TaskList } from './pages/TaskList'

export default function App() {
  return <div className="app-shell">
    <header className="topbar"><NavLink className="brand" to="/"><span>AI</span> 内容运营台</NavLink><nav><NavLink to="/">内容任务</NavLink><span className="disabled">素材库 · 下一期</span></nav></header>
    <Routes><Route path="/" element={<TaskList />} /><Route path="/tasks/new" element={<TaskCreate />} /><Route path="/tasks/:id" element={<TaskDetail />} /></Routes>
  </div>
}

