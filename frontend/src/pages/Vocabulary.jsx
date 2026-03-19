import { useEffect, useMemo, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  addVocabularyWord,
  generateVocabularyTest,
  getDueVocabulary,
  getVocabularyList,
  getVocabularyStats,
  getPrioritizedWrongReviewQueue,
  reviewVocabularyWord,
  startVocabularySession,
  submitVocabularyTest,
} from '../utils/api';

const emptyWord = {
  word: '',
  definition: '',
  examples: '',
  pronunciation: '',
  part_of_speech: '',
  tags: '',
  source_module: 'manual',
};

const learnButtons = [
  { label: '不认识', delta: -0.2 },
  { label: '模糊', delta: 0.05 },
  { label: '认识', delta: 0.2 },
];

const reviewButtons = [
  { label: 'Again', delta: -0.2 },
  { label: 'Hard', delta: -0.05 },
  { label: 'Good', delta: 0.12 },
  { label: 'Easy', delta: 0.22 },
];

function Vocabulary() {
  const navItems = [
    { to: '/', label: '🏠 首页' },
    { to: '/chat', label: '🤖 智能对话' },
    { to: '/listening', label: '🎧 听力练习' },
    { to: '/reading', label: '📚 阅读练习' },
    { to: '/writing', label: '✍️ 写作练习' },
    { to: '/speaking', label: '💬 口语练习' },
    { to: '/vocabulary', label: '📝 词汇学习' },
    { to: '/reports', label: '📊 学习报告' },
    { to: '/plans', label: '🎯 个性化计划' },
    { to: '/achievements', label: '🏆 成就中心' },
  ];

  const [words, setWords] = useState([]);
  const [dueWords, setDueWords] = useState([]);
  const [stats, setStats] = useState({ total: 0, due_count: 0, avg_mastery: 0, by_source_module: {} });
  const [wordForm, setWordForm] = useState(emptyWord);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [todayReviewed, setTodayReviewed] = useState(0);

  const [learnSession, setLearnSession] = useState([]);
  const [learnIndex, setLearnIndex] = useState(0);
  const [learning, setLearning] = useState(false);

  const [reviewQueue, setReviewQueue] = useState([]);
  const [reviewing, setReviewing] = useState(false);
  const [reviewMode, setReviewMode] = useState('due'); // due | wrong
  const [wrongWordIds, setWrongWordIds] = useState([]);
  const [wrongPriorityQueue, setWrongPriorityQueue] = useState([]);

  const [testMode, setTestMode] = useState('multiple_choice');
  const [testCount, setTestCount] = useState(5);
  const [testData, setTestData] = useState(null);
  const [testAnswers, setTestAnswers] = useState({});
  const [testResult, setTestResult] = useState(null);

  const wordById = useMemo(() => {
    const m = new Map();
    (words || []).forEach((w) => m.set(String(w.id), w));
    return m;
  }, [words]);

  const currentLearnWord = learnSession[learnIndex] || null;
  const currentReviewWord = reviewQueue[0] || null;
  const wrongWords = useMemo(
    () => wrongWordIds.map((id) => wordById.get(String(id))).filter(Boolean),
    [wrongWordIds, wordById],
  );

  const loadWrongPriorityQueue = async (ids = wrongWordIds) => {
    const uniqueIds = Array.from(new Set((ids || []).map((x) => String(x)).filter(Boolean)));
    if (uniqueIds.length === 0) {
      setWrongPriorityQueue([]);
      return [];
    }
    const queue = await getPrioritizedWrongReviewQueue(uniqueIds, 100);
    setWrongPriorityQueue(queue || []);
    return queue || [];
  };

  const loadWords = async () => {
    setLoading(true);
    setError('');
    try {
      const [rows, dueRows, statRows] = await Promise.all([
        getVocabularyList(300),
        getDueVocabulary(100),
        getVocabularyStats(),
      ]);
      setWords(rows || []);
      setDueWords(dueRows || []);
      setStats(statRows || { total: 0, due_count: 0, avg_mastery: 0, by_source_module: {} });
      if (reviewMode === 'due') {
        setReviewQueue(dueRows || []);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWords();
  }, []);

  useEffect(() => {
    loadWrongPriorityQueue().catch(() => {
      setWrongPriorityQueue([]);
    });
  }, [wrongWordIds]);

  const onSubmit = async (e) => {
    e.preventDefault();
    try {
      await addVocabularyWord({
        ...wordForm,
        examples: wordForm.examples ? wordForm.examples.split('|').map((x) => x.trim()).filter(Boolean) : [],
        tags: wordForm.tags ? wordForm.tags.split(',').map((x) => x.trim()).filter(Boolean) : [],
      });
      setWordForm(emptyWord);
      await loadWords();
    } catch (err) {
      setError(typeof err === 'string' ? err : '新增词汇失败');
    }
  };

  const onStartSession = async (strategy = 'spaced') => {
    try {
      setError('');
      setLearning(true);
      setLearnIndex(0);
      const session = await startVocabularySession(strategy, 10);
      setLearnSession(session.words || []);
    } catch (err) {
      setError(typeof err === 'string' ? err : '开启学习会话失败');
      setLearning(false);
    }
  };

  const onLearnRate = async (delta) => {
    if (!currentLearnWord) return;
    try {
      await reviewVocabularyWord(currentLearnWord.id, delta);
      setTodayReviewed((x) => x + 1);
      if (learnIndex + 1 >= learnSession.length) {
        setLearning(false);
        setLearnSession([]);
        setLearnIndex(0);
        await loadWords();
        return;
      }
      setLearnIndex((x) => x + 1);
    } catch (err) {
      setError(typeof err === 'string' ? err : '学习反馈保存失败');
    }
  };

  const startReview = async (mode = 'due') => {
    setReviewMode(mode);
    try {
      if (mode === 'wrong') {
        const prioritized = await loadWrongPriorityQueue(wrongWordIds);
        setReviewQueue(prioritized);
        setReviewing(prioritized.length > 0);
      } else {
        setReviewQueue(dueWords);
        setReviewing((dueWords || []).length > 0);
      }
    } catch (err) {
      setError(typeof err === 'string' ? err : '加载错词优先队列失败');
      if (mode === 'wrong') {
        setReviewQueue(wrongWords);
        setReviewing(wrongWords.length > 0);
      } else {
        setReviewQueue(dueWords);
        setReviewing((dueWords || []).length > 0);
      }
    }
  };

  const onReviewRate = async (delta) => {
    if (!currentReviewWord) return;
    try {
      await reviewVocabularyWord(currentReviewWord.id, delta);
      setTodayReviewed((x) => x + 1);
      const next = reviewQueue.slice(1);
      setReviewQueue(next);
      if (next.length === 0) {
        setReviewing(false);
      }
      await loadWords();
    } catch (err) {
      setError(typeof err === 'string' ? err : '复习记录失败');
    }
  };

  const onGenerateTest = async () => {
    try {
      setError('');
      const data = await generateVocabularyTest(testMode, Number(testCount) || 5);
      setTestData(data);
      setTestAnswers({});
      setTestResult(null);
    } catch (err) {
      setError(typeof err === 'string' ? err : '生成词汇测试失败');
    }
  };

  const onSubmitTest = async () => {
    try {
      if (!testData?.test_id) return;
      const answers = (testData.questions || []).map((q) => ({
        question_id: q.id,
        answer: String(testAnswers[q.id] || ''),
      }));
      const result = await submitVocabularyTest(testData.test_id, answers);
      setTestResult(result);
      const wrongIds = (result.details || [])
        .filter((d) => !d.is_correct && d.word_id)
        .map((d) => String(d.word_id));
      const uniqueWrongIds = Array.from(new Set(wrongIds));
      setWrongWordIds(uniqueWrongIds);
      await loadWrongPriorityQueue(uniqueWrongIds);
      await loadWords();
    } catch (err) {
      setError(typeof err === 'string' ? err : '提交词汇测试失败');
    }
  };

  return (
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>📝 词汇练习</h1></div>
        </div>
      </header>

      <div className="main-layout">
        <div className="sidebar">
          <div className="sidebar-header"><h2>🎓 IELTS Agent</h2></div>
          <nav className="sidebar-nav">
            <ul>
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) => `sidebar-nav-link${isActive ? ' active' : ''}`}
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <div className="content-area content-shell vocab-page">
        <div className="card vocab-card">
          <h3>今日概览</h3>
          <div className="vocab-overview-grid">
            <div className="vocab-overview-item"><span>词汇总数</span><strong>{stats.total || 0}</strong></div>
            <div className="vocab-overview-item"><span>到期复习</span><strong>{stats.due_count || 0}</strong></div>
            <div className="vocab-overview-item"><span>平均掌握度</span><strong>{Math.round((stats.avg_mastery || 0) * 100)}%</strong></div>
            <div className="vocab-overview-item"><span>今日已练</span><strong>{todayReviewed}</strong></div>
            <div className="vocab-overview-item"><span>错词待复习</span><strong>{wrongWords.length}</strong></div>
          </div>
        </div>

        <div className="card vocab-card">
          <h3>新词学习（Learn）</h3>
          <div className="vocab-actions-row">
            <button className="vocab-btn vocab-btn-primary" onClick={() => onStartSession('spaced')}>开始10词（Spaced）</button>
            <button className="vocab-btn vocab-btn-primary" onClick={() => onStartSession('root')}>开始10词（词根词缀）</button>
            <button className="vocab-btn vocab-btn-primary" onClick={() => onStartSession('context')}>开始10词（语境优先）</button>
          </div>
          {learning && currentLearnWord && (
            <div className="vocab-focus-panel">
              <p>进度：{learnIndex + 1}/{learnSession.length}</p>
              <h4 style={{ marginBottom: 6 }}>{currentLearnWord.word}</h4>
              <p>释义：{currentLearnWord.definition || '暂无释义'}</p>
              {(currentLearnWord.examples || []).length > 0 && (
                <p>例句：{currentLearnWord.examples[0]}</p>
              )}
              <div className="vocab-actions-row">
                {learnButtons.map((b) => (
                  <button className="vocab-btn vocab-btn-secondary" key={b.label} onClick={() => onLearnRate(b.delta)}>{b.label}</button>
                ))}
              </div>
            </div>
          )}
          {!learning && <p>点击按钮开始学习会话。</p>}
        </div>

        <div className="card vocab-card">
          <h3>复习巩固（Review）</h3>
          <div className="vocab-actions-row">
            <button className="vocab-btn vocab-btn-primary" onClick={() => startReview('due')}>开始到期复习</button>
            <button className="vocab-btn vocab-btn-primary" onClick={() => startReview('wrong')} disabled={wrongWords.length === 0}>仅练错词</button>
          </div>
          {reviewing && currentReviewWord && (
            <div className="vocab-focus-panel">
              <p>模式：{reviewMode === 'wrong' ? '错词专项' : '到期复习'}</p>
              {reviewMode === 'wrong' && (
                <p>
                  优先级：{Number(currentReviewWord.priority_score || 0).toFixed(3)}
                  {' · '}
                  {currentReviewWord.priority_reason || '遗忘曲线自动排序'}
                </p>
              )}
              <h4 style={{ marginBottom: 6 }}>{currentReviewWord.word}</h4>
              <p>释义：{currentReviewWord.definition || '暂无释义'}</p>
              {(currentReviewWord.examples || []).length > 0 && (
                <p>例句：{currentReviewWord.examples[0]}</p>
              )}
              <div className="vocab-actions-row">
                {reviewButtons.map((b) => (
                  <button className="vocab-btn vocab-btn-secondary" key={b.label} onClick={() => onReviewRate(b.delta)}>{b.label}</button>
                ))}
              </div>
            </div>
          )}
          {!reviewing && (
            <p>
              当前待复习：{dueWords.length}，错词待复习：{wrongWords.length}
            </p>
          )}
          {wrongPriorityQueue.length > 0 && (
            <div className="vocab-subpanel">
              <h4 style={{ marginBottom: 8 }}>错词优先队列（遗忘曲线）</h4>
              <div className="vocab-table-wrap">
              <table className="vocab-table">
                <thead>
                  <tr>
                    <th align="left">单词</th>
                    <th align="left">优先级</th>
                    <th align="left">依据</th>
                  </tr>
                </thead>
                <tbody>
                  {wrongPriorityQueue.slice(0, 8).map((w) => (
                    <tr key={w.id}>
                      <td>{w.word}</td>
                      <td>{Number(w.priority_score || 0).toFixed(3)}</td>
                      <td>{w.priority_reason || '遗忘曲线自动排序'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
              {wrongPriorityQueue.length > 8 && (
                <p style={{ marginTop: 6, opacity: 0.8 }}>
                  仅展示前 8 个高优先级词（共 {wrongPriorityQueue.length} 个）。
                </p>
              )}
            </div>
          )}
        </div>

        <div className="card vocab-card">
          <h3>词汇测试（Test）</h3>
          <div className="vocab-actions-row">
            <select value={testMode} onChange={(e) => setTestMode(e.target.value)}>
              <option value="multiple_choice">multiple_choice</option>
              <option value="spelling">spelling</option>
              <option value="fill_blank">fill_blank</option>
            </select>
            <input
              type="number"
              min="1"
              max="20"
              value={testCount}
              onChange={(e) => setTestCount(e.target.value)}
              style={{ width: 90 }}
            />
            <button className="vocab-btn vocab-btn-primary" onClick={onGenerateTest}>生成测试</button>
            <button className="vocab-btn vocab-btn-primary" onClick={onSubmitTest} disabled={!testData?.test_id}>提交测试</button>
          </div>
          {testData && (
            <div className="vocab-test-list">
              {(testData.questions || []).map((q, idx) => (
                <div key={q.id} className="vocab-test-item">
                  <p style={{ marginBottom: 6 }}>{idx + 1}. {q.prompt}</p>
                  {Array.isArray(q.options) && q.options.length > 0 ? (
                    <div style={{ display: 'grid', gap: 4 }}>
                      {q.options.map((opt) => (
                        <label key={opt}>
                          <input
                            type="radio"
                            name={q.id}
                            checked={testAnswers[q.id] === opt}
                            onChange={() => setTestAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                          />
                          {opt}
                        </label>
                      ))}
                    </div>
                  ) : (
                    <input
                      value={testAnswers[q.id] || ''}
                      onChange={(e) => setTestAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder="输入答案"
                    />
                  )}
                </div>
              ))}
            </div>
          )}
          {testResult && (
            <div style={{ marginTop: 10 }}>
              <p>得分：{testResult.correct}/{testResult.total}（accuracy: {testResult.accuracy}）</p>
              <ul>
                {(testResult.details || []).map((d) => (
                  <li key={d.question_id}>
                    {d.word}: {d.is_correct ? '✅' : `❌（你的答案: ${d.user_answer}，正确: ${d.expected_answer}）`}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="card vocab-card">
          <h3>新增词汇</h3>
          <form onSubmit={onSubmit} className="vocab-form">
            <input placeholder="word" value={wordForm.word} onChange={(e) => setWordForm({ ...wordForm, word: e.target.value })} required />
            <input placeholder="definition" value={wordForm.definition} onChange={(e) => setWordForm({ ...wordForm, definition: e.target.value })} />
            <input placeholder="examples (用 | 分隔)" value={wordForm.examples} onChange={(e) => setWordForm({ ...wordForm, examples: e.target.value })} />
            <input placeholder="pronunciation" value={wordForm.pronunciation} onChange={(e) => setWordForm({ ...wordForm, pronunciation: e.target.value })} />
            <input placeholder="part_of_speech" value={wordForm.part_of_speech} onChange={(e) => setWordForm({ ...wordForm, part_of_speech: e.target.value })} />
            <input placeholder="tags (逗号分隔)" value={wordForm.tags} onChange={(e) => setWordForm({ ...wordForm, tags: e.target.value })} />
            <button className="vocab-btn vocab-btn-primary" type="submit">添加词汇</button>
          </form>
        </div>

        <div className="card vocab-card">
          <h3>词汇本</h3>
          <button className="vocab-btn vocab-btn-secondary" onClick={loadWords}>刷新</button>
          {loading ? <p>加载中...</p> : (
            <div className="vocab-table-wrap">
            <table className="vocab-table">
              <thead>
                <tr>
                  <th align="left">单词</th>
                  <th align="left">释义</th>
                  <th align="left">掌握度</th>
                  <th align="left">标签</th>
                </tr>
              </thead>
              <tbody>
                {words.map((w) => (
                  <tr key={w.id}>
                    <td>{w.word}</td>
                    <td>{w.definition}</td>
                    <td>{Math.round((w.mastery_level || 0) * 100)}%</td>
                    <td>{(w.tags || []).join(', ')}</td>
                  </tr>
                ))}
                {words.length === 0 && (
                  <tr><td colSpan={4}>暂无词汇数据</td></tr>
                )}
              </tbody>
            </table>
            </div>
          )}
          {error && <p style={{ color: 'red' }}>{error}</p>}
        </div>
      </div>
      </div>
    </div>
  );
}

export default Vocabulary;
