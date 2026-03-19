import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { getSessionReport } from '../utils/api';

function Reports() {
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

  const [sessionId, setSessionId] = useState('');
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');

  return (
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>📊 学习报告</h1></div>
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
            <h3>查询会话报告</h3>
            <input
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="输入 session_id"
              style={{ width: '100%', marginBottom: 8 }}
            />
            <button
              onClick={async () => {
                setError('');
                try {
                  setReport(await getSessionReport(sessionId.trim()));
                } catch (e) {
                  setError(typeof e === 'string' ? e : '查询失败');
                  setReport(null);
                }
              }}
              disabled={!sessionId.trim()}
            >
              获取报告
            </button>
          </div>
          <div className="card">
            <h3>报告结果</h3>
            {report ? (
              <div>
                <p>{report.summary}</p>
                <p>scores: {JSON.stringify(report.scores)}</p>
                <h4>suggestions</h4>
                <ul>{(report.suggestions || []).map((s, idx) => <li key={idx}>{s}</li>)}</ul>
              </div>
            ) : (
              <p>暂无报告</p>
            )}
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Reports;
