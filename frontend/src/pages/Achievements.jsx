import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  getCurrentUser,
  getGamificationAchievements,
  getGamificationEvents,
  getGamificationLeaderboard,
  getGamificationOverview,
  redeemGamificationItem,
} from '../utils/api';

const Achievements = () => {
  const navItems = [
    { to: '/', label: '🏠 首页' },
    { to: '/chat', label: '🤖 智能对话' },
    { to: '/listening', label: '🎧 听力练习' },
    { to: '/reading', label: '📚 阅读练习' },
    { to: '/writing', label: '📝 写作练习' },
    { to: '/speaking', label: '💬 口语练习' },
    { to: '/vocabulary', label: '📋 词汇学习' },
    { to: '/mistakes', label: '🔖 错题本' },
    { to: '/mock-exam', label: '🎯 模拟考试' },
    { to: '/reports', label: '📊 学习报告' },
    { to: '/achievements', label: '🏆 成就中心' },
    { to: '/profile', label: '👤 个人中心' },
  ];

  const [userData, setUserData] = useState({ username: '李同学' });
  const [overview, setOverview] = useState(null);
  const [achievements, setAchievements] = useState([]);
  const [events, setEvents] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [message, setMessage] = useState('');
  const [redeeming, setRedeeming] = useState('');

  const loadData = async () => {
    try {
      const [ov, ac, ev, lb] = await Promise.all([
        getGamificationOverview(),
        getGamificationAchievements(30),
        getGamificationEvents(20),
        getGamificationLeaderboard(10),
      ]);
      setOverview(ov || null);
      setAchievements(ac || []);
      setEvents(ev || []);
      setLeaderboard(lb || []);
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '成就数据加载失败');
    }
  };

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const user = await getCurrentUser();
        if (user) setUserData(prev => ({ ...prev, username: user.username }));
      } catch (err) {
        console.error('Failed to fetch user data:', err);
      }
    };
    fetchUserData();
    loadData();
  }, []);

  const handleRedeem = async (itemCode) => {
    setRedeeming(itemCode);
    setMessage('');
    try {
      const res = await redeemGamificationItem(itemCode);
      setMessage(`兑换成功：${res.item_name}，当前积分 ${res.total_points}`);
      await loadData();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '兑换失败');
    } finally {
      setRedeeming('');
    }
  };

  return (
    <div className="dashboard-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>🎓 IELTS Agent</h1></div>
          <div className="nav-right">
            <div className="notification"><span className="icon">🔔</span><span className="badge">3</span></div>
            <div className="user-profile"><span className="avatar">👤</span><span className="username">{userData.username}</span></div>
            <div className="settings"><span className="icon">⚙️</span></div>
          </div>
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

        <div className="content-area">
          <main className="reports-content">
            <div className="page-header">
              <div className="breadcrumb"><span>首页</span> &gt; <span>成就中心</span></div>
              <h1 className="page-title">🏆 成就中心</h1>
            </div>

            {message && <div className="card"><p>{message}</p></div>}

            <div className="overview-cards" style={{ marginBottom: 16 }}>
              <div className="card">
                <h3>总积分</h3>
                <p style={{ fontSize: 28, margin: 0 }}>{overview?.total_points ?? 0}</p>
              </div>
              <div className="card">
                <h3>当前等级</h3>
                <p style={{ fontSize: 28, margin: 0 }}>{overview?.level || 'bronze'}</p>
              </div>
              <div className="card">
                <h3>事件数量</h3>
                <p style={{ fontSize: 28, margin: 0 }}>{overview?.event_count ?? 0}</p>
              </div>
              <div className="card">
                <h3>成就数量</h3>
                <p style={{ fontSize: 28, margin: 0 }}>{overview?.achievement_count ?? 0}</p>
              </div>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>积分兑换</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {(overview?.available_catalog || []).map((x) => (
                  <button key={x.item_code} onClick={() => handleRedeem(x.item_code)} disabled={redeeming === x.item_code}>
                    {redeeming === x.item_code ? '兑换中...' : `${x.item_name}（${x.cost_points}分）`}
                  </button>
                ))}
              </div>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>我的成就</h3>
              <ul>
                {achievements.map((x) => (
                  <li key={x.id}>
                    {x.icon} {x.title} - {x.description}
                  </li>
                ))}
                {achievements.length === 0 && <li>暂无成就，先去完成互评任务吧</li>}
              </ul>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>积分流水</h3>
              <ul>
                {events.map((x) => (
                  <li key={x.id}>
                    {x.note || x.source} | {x.points > 0 ? `+${x.points}` : x.points} 分
                  </li>
                ))}
                {events.length === 0 && <li>暂无积分记录</li>}
              </ul>
            </div>

            <div className="card">
              <h3>排行榜</h3>
              <ul>
                {leaderboard.map((x) => (
                  <li key={`${x.user_id}-${x.rank}`}>
                    #{x.rank} {x.user_alias} | 积分 {x.total_points} | 事件 {x.event_count}
                  </li>
                ))}
                {leaderboard.length === 0 && <li>暂无排行数据</li>}
              </ul>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default Achievements;
