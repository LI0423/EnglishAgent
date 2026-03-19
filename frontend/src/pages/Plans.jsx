import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { createLearningPlan, generatePlan7d, getPlans } from '../utils/api';

function Plans() {
  const navItems = [
    { to: '/', label: '🏠 首页' },
    { to: '/chat', label: '🤖 智能对话' },
    { to: '/listening', label: '🎧 听力练习' },
    { to: '/reading', label: '📚 阅读练习' },
    { to: '/writing', label: '📝 写作练习' },
    { to: '/speaking', label: '💬 口语练习' },
    { to: '/vocabulary', label: '📋 词汇学习' },
    { to: '/mistakes', label: '🔖 错题本' },
    { to: '/reports', label: '📊 学习报告' },
    { to: '/plans', label: '🎯 个性化计划' },
  ];

  const [plans, setPlans] = useState([]);
  const [plan7d, setPlan7d] = useState(null);
  const [error, setError] = useState('');

  const loadPlans = async () => {
    try {
      setPlans(await getPlans());
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载计划失败');
    }
  };

  useEffect(() => {
    loadPlans();
  }, []);

  return (
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>🎯 个性化计划</h1></div>
        </div>
      </header>
      <div className="main-layout">
        <div className="sidebar">
          <div className="sidebar-header"><h2>🎓 IELTS Agent</h2></div>
          <nav className="sidebar-nav">
            <ul>
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink to={item.to} end={item.to === '/'} className={({ isActive }) => `sidebar-nav-link${isActive ? ' active' : ''}`}>
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="content-area content-shell">
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>快速生成 7 天计划</h3>
            <button
              onClick={async () => {
                setError('');
                try {
                  const data = await generatePlan7d(['limited vocabulary', 'grammar errors'], 7.0, '1-2 hours');
                  setPlan7d(data);
                } catch (e) {
                  setError(typeof e === 'string' ? e : '生成失败');
                }
              }}
            >
              生成7天计划
            </button>
            {plan7d && (
              <div style={{ marginTop: 12 }}>
                <p>{plan7d.summary}</p>
                <p>total_hours: {plan7d.total_hours}</p>
                <ul>
                  {(plan7d.plan || []).map((day) => (
                    <li key={day.day}>{day.day} - {day.focus_area}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>创建长期学习计划</h3>
            <button
              onClick={async () => {
                setError('');
                try {
                  await createLearningPlan({
                    target_band: 7.0,
                    daily_minutes: 90,
                    focus_modules: ['listening', 'reading', 'writing', 'speaking'],
                    duration_weeks: 8,
                  });
                  await loadPlans();
                } catch (e) {
                  setError(typeof e === 'string' ? e : '创建失败');
                }
              }}
            >
              创建计划（示例）
            </button>
          </div>

          <div className="card">
            <h3>我的计划列表</h3>
            <button onClick={loadPlans}>刷新</button>
            <ul>
              {plans.map((p) => (
                <li key={p.id}>
                  {p.id} | target_band: {p.target_band} | daily_minutes: {p.daily_minutes} | status: {p.status}
                </li>
              ))}
              {plans.length === 0 && <li>暂无计划</li>}
            </ul>
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Plans;
