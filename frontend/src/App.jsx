import { Suspense, lazy } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import './App.css'

const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const Home = lazy(() => import('./pages/Home'))
const Chat = lazy(() => import('./pages/Chat'))
const Writing = lazy(() => import('./pages/Writing'))
const Listening = lazy(() => import('./pages/Listening'))
const Reading = lazy(() => import('./pages/Reading'))
const Speaking = lazy(() => import('./pages/Speaking'))
const Reports = lazy(() => import('./pages/Reports'))
const Plans = lazy(() => import('./pages/Plans'))
const Diagnostic = lazy(() => import('./pages/Diagnostic'))
const Mistakes = lazy(() => import('./pages/Mistakes'))
const Vocabulary = lazy(() => import('./pages/Vocabulary'))
const ComingSoon = lazy(() => import('./pages/ComingSoon'))

function RouteLoading() {
  return (
    <div style={{ padding: 24, textAlign: 'center' }}>
      页面加载中...
    </div>
  )
}

function App() {
  return (
    <Router>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/writing" element={<Writing />} />
          <Route path="/mistakes" element={<Mistakes />} />
          <Route path="/vocabulary" element={<Vocabulary />} />
          <Route path="/listening" element={<Listening />} />
          <Route path="/reading" element={<Reading />} />
          <Route path="/speaking" element={<Speaking />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/plans" element={<Plans />} />
          <Route path="/achievements" element={<ComingSoon />} />
          <Route path="/mock-exam" element={<Diagnostic />} />
          <Route path="/profile" element={<ComingSoon />} />
        </Routes>
      </Suspense>
    </Router>
  )
}

export default App
