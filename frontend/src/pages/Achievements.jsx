import { useEffect, useState } from 'react';
import {
  getCurrentUser,
  getGamificationAchievements,
  getGamificationEvents,
  getGamificationLeaderboard,
  getGamificationOverview,
  redeemGamificationItem,
} from '../utils/api';
import SidebarMenu from '../components/layout/SidebarMenu';

import TopNav from "../components/layout/TopNav";
const Achievements = () => {

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
    <div className="home-page web-dashboard dashboard-page">
      <TopNav username={userData.username} />

      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>

        <div className="content-area content-shell">
          <main className="reports-content">
            <div className="web-page-head">
              <div>
                <h2>成就中心</h2>
                <p>查看积分、成就、兑换记录与排行榜。</p>
              </div>
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
