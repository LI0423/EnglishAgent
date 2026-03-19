import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  analyzeReadingLongSentences,
  analyzeReadingPassage,
  detectReadingSynonyms,
  generateReadingQuiz,
  getReadingQuizVersion,
  submitReadingQuiz,
} from '../utils/api';

function Reading() {
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

  const [text, setText] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [synonyms, setSynonyms] = useState(null);
  const [longSentences, setLongSentences] = useState([]);
  const [quizVersion, setQuizVersion] = useState(null);
  const [quizConfig, setQuizConfig] = useState({ count: 3, difficulty: '', questionType: '' });
  const [quiz, setQuiz] = useState(null);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizResult, setQuizResult] = useState(null);
  const [error, setError] = useState('');

  const runAll = async () => {
    if (!text.trim()) return;
    setError('');
    try {
      const [a, s, l] = await Promise.all([
        analyzeReadingPassage(text),
        detectReadingSynonyms(text),
        analyzeReadingLongSentences(text),
      ]);
      setAnalysis(a);
      setSynonyms(s);
      setLongSentences(l || []);
    } catch (e) {
      setError(typeof e === 'string' ? e : '分析失败');
    }
  };

  const loadQuizVersion = async () => {
    try {
      const v = await getReadingQuizVersion();
      setQuizVersion(v || null);
    } catch {}
  };

  const handleGenerateQuiz = async () => {
    setError('');
    setQuizResult(null);
    try {
      const data = await generateReadingQuiz({
        count: Number(quizConfig.count) || 3,
        difficulty: quizConfig.difficulty || null,
        questionType: quizConfig.questionType || null,
      });
      setQuiz(data || null);
      setQuizAnswers({});
    } catch (e) {
      setError(typeof e === 'string' ? e : '生成阅读测验失败');
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
      const result = await submitReadingQuiz(quiz.quiz_id, answers);
      setQuizResult(result || null);
    } catch (e) {
      setError(typeof e === 'string' ? e : '提交阅读测验失败');
    }
  };

  useEffect(() => {
    loadQuizVersion();
  }, []);

  return (
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>📚 阅读练习</h1></div>
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
            <h3>阅读文本输入</h3>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="粘贴一段阅读文本进行同义替换、难度与长难句分析"
              rows={10}
              style={{ width: '100%' }}
            />
            <div style={{ marginTop: 8 }}>
              <button onClick={runAll} disabled={!text.trim()}>一键分析</button>
            </div>
          </div>

          {analysis && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3>篇章分析</h3>
              <p>难度：{analysis.difficulty?.level}</p>
              <p>原因：{analysis.difficulty?.reason}</p>
              <p>同义替换命中：{analysis.synonym_count}</p>
              <p>长句数量：{analysis.long_sentence_count}</p>
            </div>
          )}

          {synonyms && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3>同义替换识别</h3>
              <p>{synonyms.summary}</p>
              <ul>
                {(synonyms.results || []).map((item, idx) => (
                  <li key={idx}>
                    <strong>{item.original}</strong> → {(item.synonyms || []).join(', ')}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card">
            <h3>长难句分析</h3>
            <ul>
              {longSentences.map((item, idx) => (
                <li key={idx}>
                  <p>{item.original}</p>
                  <p>简化：{item.simplified}</p>
                </li>
              ))}
              {longSentences.length === 0 && <li>暂无长难句结果</li>}
            </ul>
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3>阅读测验</h3>
            <p style={{ fontSize: 12, color: '#666' }}>
              题库版本: {quizVersion?.version || '-'} ({quizVersion?.source || '-'})
            </p>
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
                  <option value="basic">basic</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
              </label>
              <label>
                题型
                <select
                  value={quizConfig.questionType}
                  onChange={(e) => setQuizConfig((prev) => ({ ...prev, questionType: e.target.value }))}
                  style={{ marginLeft: 6 }}
                >
                  <option value="">全部</option>
                  <option value="tfng">tfng</option>
                  <option value="heading_matching">heading_matching</option>
                  <option value="attitude">attitude</option>
                  <option value="inference">inference</option>
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
                      type: {q.question_type} | difficulty: {q.difficulty}
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
                  onClick={() => navigate('/mistakes?module=reading&questionType=reading_quiz')}
                  style={{ marginBottom: 10 }}
                >
                  查看本次阅读错题
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Reading;
