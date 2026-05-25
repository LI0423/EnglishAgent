import { Suspense, lazy, useEffect } from 'react'
import { BrowserRouter as Router, Navigate, Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import './App.css'

const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const Home = lazy(() => import('./pages/Home'))
const Chat = lazy(() => import('./pages/Chat'))
const TranslationSearch = lazy(() => import('./pages/TranslationSearch'))
const Writing = lazy(() => import('./pages/Writing'))
const Listening = lazy(() => import('./pages/Listening'))
const Reading = lazy(() => import('./pages/Reading'))
const Speaking = lazy(() => import('./pages/Speaking'))
const Reports = lazy(() => import('./pages/Reports'))
const Plans = lazy(() => import('./pages/Plans'))
const ReminderCenter = lazy(() => import('./pages/ReminderCenter'))
const Diagnostic = lazy(() => import('./pages/Diagnostic'))
const Mistakes = lazy(() => import('./pages/Mistakes'))
const Vocabulary = lazy(() => import('./pages/Vocabulary'))
const Achievements = lazy(() => import('./pages/Achievements'))
const Community = lazy(() => import('./pages/Community'))
const StudyGroups = lazy(() => import('./pages/StudyGroups'))
const PaymentCenter = lazy(() => import('./pages/PaymentCenter'))
const Admin = lazy(() => import('./pages/Admin'))
const Campaigns = lazy(() => import('./pages/Campaigns'))
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

function hasStoredToken() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    return Boolean(user?.access_token || user?.token || user?.data?.access_token)
  } catch {
    return false
  }
}

function RequireAuth({ children }) {
  const location = useLocation()
  if (!hasStoredToken()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return children
}

const protectedRoute = (element) => (
  <RequireAuth>
    {element}
  </RequireAuth>
)

function App() {
  return (
    <Router>
      <AuthSessionWatcher />
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={protectedRoute(<Home />)} />
          <Route path="/chat" element={protectedRoute(<Chat />)} />
          <Route path="/translation-search" element={protectedRoute(<TranslationSearch />)} />
          <Route path="/writing" element={protectedRoute(<Writing />)} />
          <Route path="/mistakes" element={protectedRoute(<Mistakes />)} />
          <Route path="/vocabulary" element={protectedRoute(<Vocabulary />)} />
          <Route path="/community" element={protectedRoute(<Community />)} />
          <Route path="/groups" element={protectedRoute(<StudyGroups />)} />
          <Route path="/payment" element={protectedRoute(<PaymentCenter />)} />
          <Route path="/admin" element={protectedRoute(<Admin />)} />
          <Route path="/campaigns" element={protectedRoute(<Campaigns />)} />
          <Route path="/listening" element={protectedRoute(<Listening />)} />
          <Route path="/reading" element={protectedRoute(<Reading />)} />
          <Route path="/speaking" element={protectedRoute(<Speaking />)} />
          <Route path="/reports" element={protectedRoute(<Reports />)} />
          <Route path="/plans" element={protectedRoute(<Plans />)} />
          <Route path="/reminders" element={protectedRoute(<ReminderCenter />)} />
          <Route path="/achievements" element={protectedRoute(<Achievements />)} />
          <Route path="/mock-exam" element={protectedRoute(<Diagnostic />)} />
          <Route path="/profile" element={protectedRoute(<ComingSoon />)} />
        </Routes>
      </Suspense>
    </Router>
  )
}

export default App
