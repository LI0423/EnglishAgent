import { useEffect, useMemo, useState } from 'react';
import {
  createCampaign,
  getCampaignMe,
  getCampaigns,
  getCampaignStats,
  getCurrentUser,
  joinCampaign,
  reportCampaignEvent,
  setCampaignStatus,
} from '../utils/api';
import SidebarMenu from '../components/layout/SidebarMenu';

import TopNav from "../components/layout/TopNav";
const Campaigns = () => {

  const [userData, setUserData] = useState({ username: '同学' });
  const [campaigns, setCampaigns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [myJoin, setMyJoin] = useState(null);
  const [stats, setStats] = useState(null);
  const [message, setMessage] = useState('');

  const [formTitle, setFormTitle] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formType, setFormType] = useState('challenge');
  const [formTarget, setFormTarget] = useState(5);
  const [formReward, setFormReward] = useState(8);
  const [formDays, setFormDays] = useState(7);

  const nowSec = useMemo(() => Math.floor(Date.now() / 1000), []);

  const loadCampaigns = async () => {
    const rows = await getCampaigns('');
    setCampaigns(rows || []);
  };

  const loadSelectedDetail = async (campaign) => {
    setSelected(campaign);
    try {
      const [me, st] = await Promise.all([
        getCampaignMe(campaign.id),
        getCampaignStats(campaign.id),
      ]);
      setMyJoin(me || null);
      setStats(st || null);
    } catch {
      setMyJoin(null);
      setStats(null);
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const user = await getCurrentUser();
        if (user) setUserData(prev => ({ ...prev, username: user.username }));
      } catch {
        // ignore
      }
      await loadCampaigns();
    };
    bootstrap();
  }, []);

  const handleCreateCampaign = async () => {
    if (!formTitle.trim()) return;
    try {
      const startAt = nowSec;
      const endAt = nowSec + Number(formDays || 7) * 86400;
      const created = await createCampaign({
        title: formTitle.trim(),
        description: formDesc.trim(),
        campaign_type: formType,
        start_at: startAt,
        end_at: endAt,
        reward_points: Number(formReward || 0),
        target: Number(formTarget || 1),
        auto_start: true,
      });
      setMessage(`活动创建成功：${created.title}`);
      setFormTitle('');
      setFormDesc('');
      await loadCampaigns();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '创建活动失败（需管理员权限）');
    }
  };

  const handleJoin = async () => {
    if (!selected?.id) return;
    try {
      const joined = await joinCampaign(selected.id);
      setMyJoin(joined);
      setMessage('报名成功');
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '报名失败');
    }
  };

  const handleAdvance = async () => {
    if (!selected?.id) return;
    try {
      const updated = await reportCampaignEvent(selected.id, {
        event_type: 'manual_progress',
        value: 1,
        metadata: { source: 'campaign_page' },
      });
      setMyJoin(updated);
      setMessage(updated.status === 'completed' ? '恭喜完成活动，奖励已发放' : '进度 +1');
      try {
        const st = await getCampaignStats(selected.id);
        setStats(st || null);
      } catch {
        // ignore
      }
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '上报进度失败');
    }
  };

  const handleSetStatus = async (status) => {
    if (!selected?.id) return;
    try {
      await setCampaignStatus(selected.id, status);
      setMessage(`活动状态已更新为 ${status}`);
      await loadCampaigns();
      const fresh = (campaigns || []).find((x) => x.id === selected.id);
      if (fresh) setSelected({ ...fresh, status });
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '状态更新失败（需管理员权限）');
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
                <h2>活动中心</h2>
                <p>创建活动、报名挑战并跟踪活动完成进度。</p>
              </div>
            </div>
            {message && <div className="card"><p>{message}</p></div>}

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>创建活动（管理员）</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <input value={formTitle} onChange={(e) => setFormTitle(e.target.value)} placeholder="活动标题" />
                <input value={formDesc} onChange={(e) => setFormDesc(e.target.value)} placeholder="活动描述" style={{ minWidth: 260, flex: 1 }} />
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <select value={formType} onChange={(e) => setFormType(e.target.value)}>
                  <option value="challenge">challenge</option>
                  <option value="checkin">checkin</option>
                  <option value="competition">competition</option>
                </select>
                <input type="number" min="1" value={formTarget} onChange={(e) => setFormTarget(e.target.value)} placeholder="目标次数" />
                <input type="number" min="0" value={formReward} onChange={(e) => setFormReward(e.target.value)} placeholder="奖励积分" />
                <input type="number" min="1" value={formDays} onChange={(e) => setFormDays(e.target.value)} placeholder="持续天数" />
                <button onClick={handleCreateCampaign}>创建活动</button>
              </div>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>活动列表</h3>
              <ul>
                {campaigns.map((c) => (
                  <li key={c.id} style={{ marginBottom: 8 }}>
                    <strong>{c.title}</strong> | {c.campaign_type} | 状态 {c.status} | 奖励 {c.reward_points} 分
                    <br />
                    目标 {c.target} 次 | 时间 {new Date(c.start_at * 1000).toLocaleDateString()} ~ {new Date(c.end_at * 1000).toLocaleDateString()}
                    <br />
                    <button onClick={() => loadSelectedDetail(c)}>查看详情</button>
                  </li>
                ))}
                {campaigns.length === 0 && <li>暂无活动</li>}
              </ul>
            </div>

            {selected && (
              <div className="card">
                <h3>活动详情：{selected.title}</h3>
                <p>{selected.description || '暂无描述'}</p>
                <p>状态：{selected.status} | 目标：{selected.target} | 奖励：{selected.reward_points} 分</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                  <button onClick={handleJoin}>报名参与</button>
                  <button onClick={handleAdvance}>上报一次进度</button>
                  <button onClick={() => handleSetStatus('active')}>设为 active</button>
                  <button onClick={() => handleSetStatus('ended')}>设为 ended</button>
                </div>
                {myJoin && (
                  <p>我的进度：{myJoin.progress}/{myJoin.target}（{myJoin.status}）</p>
                )}
                {stats && (
                  <p>参与人数：{stats.participant_count} | 完成人数：{stats.completed_count} | 完成率：{stats.completion_rate}% | 事件量：{stats.event_count}</p>
                )}
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default Campaigns;
