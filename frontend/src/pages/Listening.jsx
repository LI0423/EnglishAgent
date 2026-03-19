import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  generateListeningQuiz,
  getListeningLibrary,
  getListeningLibraryVersion,
  getListeningQuizVersion,
  getListeningStatus,
  pauseListening,
  resumeListening,
  setListeningSpeed,
  startListening,
  stopListening,
  submitListeningQuiz,
} from '../utils/api';

function Listening() {
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

  const [library, setLibrary] = useState([]);
  const [libraryVersion, setLibraryVersion] = useState(null);
  const [quizVersion, setQuizVersion] = useState(null);
  const [status, setStatus] = useState({});
  const [quizConfig, setQuizConfig] = useState({ count: 3, difficulty: '' });
  const [quiz, setQuiz] = useState(null);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizResult, setQuizResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [lib, st, lv, qv] = await Promise.all([
        getListeningLibrary(),
        getListeningStatus(),
        getListeningLibraryVersion(),
        getListeningQuizVersion(),
      ]);
      setLibrary(lib || []);
      setStatus(st || {});
      setLibraryVersion(lv || null);
      setQuizVersion(qv || null);
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const safeControl = async (fn) => {
    setError('');
    try {
      const next = await fn();
      if (next) {
        setStatus(next);
      }
    } catch (e) {
      setError(typeof e === 'string' ? e : '操作失败');
    }
  };

  const handleGenerateQuiz = async () => {
    setError('');
    setQuizResult(null);
    try {
      const data = await generateListeningQuiz({
        count: Number(quizConfig.count) || 3,
        difficulty: quizConfig.difficulty || null,
      });
      setQuiz(data || null);
      setQuizAnswers({});
    } catch (e) {
      setError(typeof e === 'string' ? e : '生成测验失败');
    }
  };

  const handleSubmitQuiz = async () => {
    if (!quiz?.quiz_id) return;
    setError('');
    try {
      const answers = (quiz.questions || []).map((q) => ({
        question_id: q.id,
        answer: quizAnswers[q.id] || '',
      }));
      const result = await submitListeningQuiz(quiz.quiz_id, answers);
      setQuizResult(result || null);
    } catch (e) {
      setError(typeof e === 'string' ? e : '提交测验失败');
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>🎧 听力练习</h1></div>
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
            <h3>播放状态</h3>
            <p>audio_id: {status.audio_id || '无'}</p>
            <p>is_playing: {String(status.is_playing || false)}</p>
            <p>speed: {status.speed || 1.0}x</p>
            <p>
              素材库版本: {libraryVersion?.version || '-'} ({libraryVersion?.source || '-'}) |
              题库版本: {quizVersion?.version || '-'} ({quizVersion?.source || '-'})
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button onClick={() => safeControl(() => pauseListening(status.current_time || 0))}>暂停</button>
              <button onClick={() => safeControl(() => resumeListening(status.current_time || 0))}>继续</button>
              <button onClick={() => safeControl(() => stopListening())}>停止</button>
              <button onClick={() => safeControl(() => setListeningSpeed(0.8))}>0.8x</button>
              <button onClick={() => safeControl(() => setListeningSpeed(1.0))}>1.0x</button>
              <button onClick={() => safeControl(() => setListeningSpeed(1.25))}>1.25x</button>
              <button onClick={loadData}>刷新</button>
            </div>
          </div>

          <div className="card">
            <h3>听力素材库（最小可用）</h3>
            {loading ? <p>加载中...</p> : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th align="left">标题</th>
                    <th align="left">难度</th>
                    <th align="left">时长(秒)</th>
                    <th align="left">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {library.map((item) => (
                    <tr key={item.id}>
                      <td>{item.title}</td>
                      <td>{item.difficulty}</td>
                      <td>{item.duration}</td>
                      <td>
                        <button
                          onClick={() => safeControl(() => startListening(item.id, 0))}
                        >
                          开始播放
                        </button>
                      </td>
                    </tr>
                  ))}
                  {library.length === 0 && (
                    <tr><td colSpan={4}>暂无听力素材</td></tr>
                  )}
                </tbody>
              </table>
            )}
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3>听力测验</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
              <label>
                题数
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={quizConfig.count}
                  onChange={(e) => setQuizConfig((prev) => ({ ...prev, count: e.target.value }))}
                  style={{ marginLeft: 6, width: 80 }}
                />
              </label>
              <label>
                难度
                <select
                  value={quizConfig.difficulty}
                  onChange={(e) => setQuizConfig((prev) => ({ ...prev, difficulty: e.target.value }))}
                  style={{ marginLeft: 6 }}
                >
                  <option value="">全部</option>
                  <option value="easy">easy</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
              </label>
              <button onClick={handleGenerateQuiz}>生成测验</button>
            </div>

            {!quiz && <p>点击“生成测验”开始答题。</p>}
            {quiz?.questions?.length > 0 && (
              <div>
                {quiz.questions.map((q, idx) => (
                  <div key={q.id} style={{ border: '1px solid #eee', borderRadius: 8, padding: 10, marginBottom: 10 }}>
                    <p style={{ marginBottom: 8 }}>
                      {idx + 1}. {q.prompt}
                    </p>
                    <p style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
                      audio: {q.audio_id} | difficulty: {q.difficulty}
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {(q.options || []).map((opt) => (
                        <label key={`${q.id}-${opt}`} style={{ cursor: 'pointer' }}>
                          <input
                            type="radio"
                            name={`q-${q.id}`}
                            value={opt}
                            checked={quizAnswers[q.id] === opt}
                            onChange={(e) => setQuizAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                            style={{ marginRight: 6 }}
                          />
                          {opt}
                        </label>
                      ))}
                      {!q.options && (
                        <input
                          type="text"
                          value={quizAnswers[q.id] || ''}
                          onChange={(e) => setQuizAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                          placeholder="输入答案"
                        />
                      )}
                    </div>
                  </div>
                ))}
                <button onClick={handleSubmitQuiz}>提交测验</button>
              </div>
            )}

            {quizResult && (
              <div style={{ marginTop: 12 }}>
                <h4>测验结果</h4>
                <p>
                  正确率: {quizResult.correct}/{quizResult.total} ({Math.round((quizResult.accuracy || 0) * 100)}%)
                </p>
                <button
                  onClick={() => navigate('/mistakes?module=listening&questionType=listening_quiz')}
                  style={{ marginBottom: 10 }}
                >
                  查看本次听力错题
                </button>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th align="left">question_id</th>
                      <th align="left">audio_id</th>
                      <th align="left">结果</th>
                      <th align="left">你的答案</th>
                      <th align="left">正确答案</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(quizResult.details || []).map((d) => (
                      <tr key={d.question_id}>
                        <td>{d.question_id}</td>
                        <td>{d.audio_id}</td>
                        <td>{d.is_correct ? '✅' : '❌'}</td>
                        <td>{d.user_answer || '-'}</td>
                        <td>{d.expected_answer || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Listening;
