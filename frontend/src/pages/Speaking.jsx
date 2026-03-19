import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  createSpeakingSession,
  finishSpeakingSession,
  listSpeakingSessions,
  scoreSpeaking,
  startSpeakingPart,
  uploadSpeakingText,
} from '../utils/api';

function Speaking() {
  const navigate = useNavigate();
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

  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState('');
  const [textPartial, setTextPartial] = useState('');
  const [transcriptId, setTranscriptId] = useState('');
  const [scoreResult, setScoreResult] = useState(null);
  const [error, setError] = useState('');

  const loadSessions = async () => {
    try {
      setSessions(await listSpeakingSessions(30, 0));
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载会话失败');
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  return (
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>💬 口语练习</h1></div>
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
            <h3>会话控制</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                onClick={async () => {
                  const s = await createSpeakingSession();
                  setCurrentSessionId(s.sessionId);
                  await loadSessions();
                }}
              >
                创建会话
              </button>
              <button
                disabled={!currentSessionId}
                onClick={async () => {
                  await startSpeakingPart(currentSessionId, 1);
                }}
              >
                开始 Part1
              </button>
              <button
                disabled={!currentSessionId || !textPartial.trim()}
                onClick={async () => {
                  await uploadSpeakingText(currentSessionId, textPartial);
                  setTextPartial('');
                }}
              >
                上传文本片段
              </button>
              <button
                disabled={!currentSessionId}
                onClick={async () => {
                  const finished = await finishSpeakingSession(currentSessionId);
                  setTranscriptId(finished.transcriptId);
                  await loadSessions();
                }}
              >
                完成会话
              </button>
              <button
                disabled={!transcriptId}
                onClick={async () => {
                  const result = await scoreSpeaking(transcriptId);
                  setScoreResult(result);
                }}
              >
                评分
              </button>
            </div>
            <p style={{ marginTop: 8 }}>当前会话：{currentSessionId || '无'}</p>
            <p>transcriptId：{transcriptId || '无'}</p>
            <textarea
              value={textPartial}
              onChange={(e) => setTextPartial(e.target.value)}
              rows={4}
              placeholder="输入口语转写片段..."
              style={{ width: '100%', marginTop: 8 }}
            />
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>历史会话</h3>
            <button onClick={loadSessions}>刷新</button>
            <ul>
              {sessions.map((s) => (
                <li key={s.id}>
                  {s.id} | topic: {s.topic || 'General'} | transcript: {s.transcript_id || '-'}
                  <button style={{ marginLeft: 8 }} onClick={() => setCurrentSessionId(s.id)}>设为当前</button>
                </li>
              ))}
              {sessions.length === 0 && <li>暂无会话</li>}
            </ul>
          </div>

          <div className="card">
            <h3>评分结果</h3>
            {scoreResult ? (
              <div>
                <p>overall: {scoreResult.overall}</p>
                <p>FC: {scoreResult.scores?.FC} | LR: {scoreResult.scores?.LR} | GR: {scoreResult.scores?.GR} | PR: {scoreResult.scores?.PR}</p>
                <button
                  onClick={() => navigate('/mistakes?module=speaking&questionType=speaking_assessment')}
                  style={{ marginBottom: 8 }}
                >
                  查看口语薄弱项
                </button>
                <ul>
                  {(scoreResult.rationales || []).map((r, idx) => <li key={idx}>{r}</li>)}
                </ul>
              </div>
            ) : <p>暂无评分结果</p>}
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Speaking;
