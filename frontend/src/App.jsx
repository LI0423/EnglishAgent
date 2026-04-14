import { Suspense, lazy, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, useLocation, useNavigate } from 'react-router-dom'
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
const Achievements = lazy(() => import('./pages/Achievements'))
const Community = lazy(() => import('./pages/Community'))
const StudyGroups = lazy(() => import('./pages/StudyGroups'))
const PaymentCenter = lazy(() => import('./pages/PaymentCenter'))
const Admin = lazy(() => import('./pages/Admin'))
const ComingSoon = lazy(() => import('./pages/ComingSoon'))

function RouteLoading() {
  return (
    <div style={{ padding: 24, textAlign: 'center' }}>
      页面加载中...
    </div>
  )
}

function AuthSessionWatcher() {
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const onAuthExpired = (event) => {
      const message = event?.detail?.message || '登录状态已失效，请重新登录'
      if (location.pathname === '/login') return
      sessionStorage.setItem('login_notice', message)
      navigate('/login', { replace: true })
    }
    window.addEventListener('auth:expired', onAuthExpired)
    return () => window.removeEventListener('auth:expired', onAuthExpired)
  }, [location.pathname, navigate])

  return null
}

function App() {
  return (
    <Router>
      <AuthSessionWatcher />
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/writing" element={<Writing />} />
          <Route path="/mistakes" element={<Mistakes />} />
          <Route path="/vocabulary" element={<Vocabulary />} />
          <Route path="/community" element={<Community />} />
          <Route path="/groups" element={<StudyGroups />} />
          <Route path="/payment" element={<PaymentCenter />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/listening" element={<Listening />} />
          <Route path="/reading" element={<Reading />} />
          <Route path="/speaking" element={<Speaking />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/plans" element={<Plans />} />
          <Route path="/achievements" element={<Achievements />} />
          <Route path="/mock-exam" element={<Diagnostic />} />
          <Route path="/profile" element={<ComingSoon />} />
        </Routes>
      </Suspense>
    </Router>
  )
}

export default App
