import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { MessageSquare, FileEdit, BookOpen, Settings } from 'lucide-react'
import ChatPage from './pages/ChatPage'
import EditorPage from './pages/EditorPage'
import LibraryPage from './pages/LibraryPage'
import SettingsPage from './pages/SettingsPage'

const navItems = [
  { to: '/', icon: MessageSquare, label: '对话' },
  { to: '/editor', icon: FileEdit, label: '编辑器' },
  { to: '/library', icon: BookOpen, label: '文献' },
  { to: '/settings', icon: Settings, label: '设置' },
]

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-background">
        {/* 侧边导航栏 */}
        <nav className="flex w-16 flex-col items-center border-r border-border bg-muted/30 py-4 gap-2">
          <div className="mb-4 text-2xl font-bold text-primary">A</div>
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center w-12 h-12 rounded-lg text-xs transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`
              }
            >
              <Icon className="h-5 w-5 mb-0.5" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* 主内容区 */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/editor" element={<EditorPage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
