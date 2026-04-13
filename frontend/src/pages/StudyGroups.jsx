import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  checkinStudyGroup,
  createStudyGroup,
  getCurrentUser,
  getMyStudyGroups,
  getStudyGroupCheckins,
  getStudyGroupLeaderboard,
  getStudyGroups,
  joinStudyGroup,
} from '../utils/api';

const StudyGroups = () => {
  const navItems = [
    { to: '/', label: '🏠 首页' },
    { to: '/community', label: '👥 学习社区' },
    { to: '/groups', label: '👨‍👩‍👧‍👦 学习小组' },
    { to: '/plans', label: '🎯 学习计划' },
    { to: '/reports', label: '📊 学习报告' },
    { to: '/achievements', label: '🏆 成就中心' },
  ];

  const [userData, setUserData] = useState({ username: '李同学' });
  const [groups, setGroups] = useState([]);
  const [myGroups, setMyGroups] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [checkins, setCheckins] = useState([]);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newMax, setNewMax] = useState(20);
  const [checkinNote, setCheckinNote] = useState('');
  const [message, setMessage] = useState('');

  const loadGroups = async () => {
    const [publicGroups, mine] = await Promise.all([
      getStudyGroups(50, 0),
      getMyStudyGroups(50),
    ]);
    setGroups(publicGroups || []);
    setMyGroups(mine || []);
  };

  const loadGroupData = async (groupId) => {
    const [board, rows] = await Promise.all([
      getStudyGroupLeaderboard(groupId, 30),
      getStudyGroupCheckins(groupId, 120),
    ]);
    setLeaderboard(board || []);
    setCheckins(rows || []);
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const user = await getCurrentUser();
        if (user) setUserData(prev => ({ ...prev, username: user.username }));
      } catch {
        // ignore
      }
      await loadGroups();
    };
    bootstrap();
  }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const res = await createStudyGroup({
        name: newName.trim(),
        description: newDesc.trim(),
        is_public: true,
        max_members: Number(newMax || 20),
      });
      setMessage(`创建成功：${res.name}`);
      setNewName('');
      setNewDesc('');
      setNewMax(20);
      await loadGroups();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '创建失败');
    }
  };

  const handleJoin = async (groupId) => {
    try {
      await joinStudyGroup(groupId);
      setMessage('加入成功');
      await loadGroups();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '加入失败');
    }
  };

  const handleSelect = async (group) => {
    setSelectedGroup(group);
    await loadGroupData(group.id);
  };

  const handleCheckin = async () => {
    if (!selectedGroup?.id) return;
    try {
      const res = await checkinStudyGroup(selectedGroup.id, { note: checkinNote, score: 2 });
      setMessage(`打卡成功：${res.note || '今日学习已记录'}`);
      setCheckinNote('');
      await Promise.all([loadGroupData(selectedGroup.id), loadGroups()]);
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '打卡失败');
    }
  };

  return (
    <div className="dashboard-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>🎓 IELTS Agent</h1></div>
          <div className="nav-right">
            <div className="user-profile"><span className="avatar">👤</span><span className="username">{userData.username}</span></div>
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
              <div className="breadcrumb"><span>首页</span> &gt; <span>学习小组</span></div>
              <h1 className="page-title">👨‍👩‍👧‍👦 学习小组</h1>
            </div>

            {message && <div className="card"><p>{message}</p></div>}

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>创建小组</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="小组名称" />
                <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="小组描述" style={{ minWidth: 280, flex: 1 }} />
                <input type="number" min="2" max="200" value={newMax} onChange={(e) => setNewMax(e.target.value)} style={{ width: 120 }} />
                <button onClick={handleCreate}>创建</button>
              </div>
            </div>

            <div className="overview-cards" style={{ marginBottom: 16 }}>
              <div className="card"><h3>我的小组数</h3><p className="big-number">{myGroups.length}</p></div>
              <div className="card"><h3>公开小组</h3><p className="big-number">{groups.length}</p></div>
              <div className="card"><h3>当前查看</h3><p className="small-text">{selectedGroup?.name || '未选择'}</p></div>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>公开小组列表</h3>
              <ul>
                {groups.map((g) => (
                  <li key={g.id} style={{ marginBottom: 8 }}>
                    <strong>{g.name}</strong> | {g.member_count}/{g.max_members} 人
                    <br />
                    {g.description || '暂无描述'}
                    <br />
                    <button onClick={() => handleSelect(g)}>查看</button>{' '}
                    <button onClick={() => handleJoin(g.id)}>加入</button>
                  </li>
                ))}
                {groups.length === 0 && <li>暂无小组</li>}
              </ul>
            </div>

            {selectedGroup && (
              <div className="card">
                <h3>小组详情：{selectedGroup.name}</h3>
                <div style={{ marginBottom: 8 }}>
                  <input value={checkinNote} onChange={(e) => setCheckinNote(e.target.value)} placeholder="今天完成了什么（可选）" style={{ minWidth: 280, marginRight: 8 }} />
                  <button onClick={handleCheckin}>今日打卡</button>
                </div>
                <h4>组内排行</h4>
                <ul>
                  {leaderboard.map((m, idx) => (
                    <li key={`${m.user_id}-${idx}`}>
                      #{idx + 1} {m.user_alias} | 累计打卡 {m.total_checkins} | 连续 {m.checkin_streak}
                    </li>
                  ))}
                  {leaderboard.length === 0 && <li>暂无排行</li>}
                </ul>
                <h4>最近打卡</h4>
                <ul>
                  {checkins.map((c) => (
                    <li key={c.id}>
                      {c.user_alias}：{c.note || '完成学习打卡'}（score {c.score}）
                    </li>
                  ))}
                  {checkins.length === 0 && <li>暂无打卡记录</li>}
                </ul>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default StudyGroups;
