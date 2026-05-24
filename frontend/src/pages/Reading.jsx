import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  autoCollectVocabulary,
  analyzeReadingLongSentences,
  analyzeReadingPassage,
  detectReadingSynonyms,
  generateContextReplay,
  generateReadingQuiz,
  generateReadingStrategyDrill,
  getReadingQuizVersion,
  submitReadingStrategyDrill,
  submitReadingQuiz,
} from '../utils/api';
import { PageSection, ToolbarRow } from '../components/layout/DesktopUI';
import SidebarMenu from '../components/layout/SidebarMenu';

import TopNav from "../components/layout/TopNav";
function Reading() {
  const navigate = useNavigate();
  const location = useLocation();

  const [text, setText] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [synonyms, setSynonyms] = useState(null);
  const [longSentences, setLongSentences] = useState([]);
  const [quizVersion, setQuizVersion] = useState(null);
  const [quizConfig, setQuizConfig] = useState({ count: 3, difficulty: '', questionType: '' });
  const [quiz, setQuiz] = useState(null);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizResult, setQuizResult] = useState(null);
  const [strategyConfig, setStrategyConfig] = useState({ mode: 'skim', count: 3, difficulty: '' });
  const [strategySession, setStrategySession] = useState(null);
  const [strategyAnswers, setStrategyAnswers] = useState({});
  const [strategySpent, setStrategySpent] = useState({});
  const [strategyStartAt, setStrategyStartAt] = useState({});
  const [strategyResult, setStrategyResult] = useState(null);
  const [autoCollectSummary, setAutoCollectSummary] = useState(null);
  const [replayNotice, setReplayNotice] = useState('');
  const [error, setError] = useState('');
  const quizCardRef = useRef(null);

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
    setAutoCollectSummary(null);
    try {
      const answers = (quiz.questions || []).map((q) => ({
        question_id: q.id,
        answer: quizAnswers[q.id] || '',
      }));
      const result = await submitReadingQuiz(quiz.quiz_id, answers);
      setQuizResult(result || null);
      const wrongDetails = (result?.details || []).filter((d) => !d.is_correct);
      if (wrongDetails.length > 0) {
        const promptById = new Map((quiz.questions || []).map((q) => [q.id, q.prompt]));
        const corpus = wrongDetails
          .map((d) => {
            const prompt = promptById.get(d.question_id) || '';
            return `${prompt} Expected: ${d.expected_answer || ''}`;
          })
          .join('\n');
        const collectRes = await autoCollectVocabulary(corpus, 'reading', 'quiz_wrong', 20);
        setAutoCollectSummary(collectRes || null);
        const wordIds = Array.isArray(collectRes?.word_ids) ? collectRes.word_ids.filter(Boolean) : [];
        if (wordIds.length > 0) {
          const replay = await generateContextReplay({
            count: Math.min(8, wordIds.length),
            sourceModule: 'reading',
            topic: 'quiz_wrong',
            mode: 'cloze',
            wordIds,
          });
          if (replay?.session_id) {
            localStorage.setItem('vocab_context_replay_prefill', JSON.stringify(replay));
          }
        }
      }
    } catch (e) {
      setError(typeof e === 'string' ? e : '提交阅读测验失败');
    }
  };

  const handleGenerateStrategy = async () => {
    setError('');
    setStrategyResult(null);
    try {
      const data = await generateReadingStrategyDrill({
        mode: strategyConfig.mode || 'skim',
        count: Number(strategyConfig.count) || 3,
        difficulty: strategyConfig.difficulty || null,
      });
      setStrategySession(data || null);
      setStrategyAnswers({});
      setStrategySpent({});
      const now = Date.now();
      const nextStartAt = {};
      (data?.questions || []).forEach((q) => {
        nextStartAt[q.id] = now;
      });
      setStrategyStartAt(nextStartAt);
    } catch (e) {
      setError(typeof e === 'string' ? e : '生成阅读策略训练失败');
    }
  };

  const handleSubmitStrategy = async () => {
    if (!strategySession?.session_id) return;
    setError('');
    try {
      const now = Date.now();
      const answers = (strategySession.questions || []).map((q) => {
        const stored = Number(strategySpent[q.id] || 0);
        const fallback = Math.max(1, Math.round((now - Number(strategyStartAt[q.id] || now)) / 1000));
        return {
          question_id: q.id,
          answer: strategyAnswers[q.id] || '',
          spent_seconds: stored > 0 ? stored : fallback,
        };
      });
      const result = await submitReadingStrategyDrill(strategySession.session_id, answers);
      setStrategyResult(result || null);
    } catch (e) {
      setError(typeof e === 'string' ? e : '提交阅读策略训练失败');
    }
  };

  useEffect(() => {
    loadQuizVersion();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search || '');
    if (params.get('replay') !== '1') return;
    const questionId = params.get('questionId') || '';
    setReplayNotice(questionId ? `来自错题重练：题目 ${questionId}` : '来自错题重练：请优先完成一次阅读测验');
    const timer = window.setTimeout(() => {
      quizCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(timer);
  }, [location.search]);

  return (
    <div className="home-page web-dashboard reading-page">
      <TopNav />
      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>

        <div className="content-area content-shell">
          <div className="web-page-head">
            <div>
              <h2>阅读练习</h2>
              <p>阅读分析、策略训练与测验结果在同一页面闭环。</p>
            </div>
            <div className="web-page-head-actions">
              <button onClick={loadQuizVersion}>刷新题库</button>
            </div>
          </div>
          {replayNotice && (
            <div className="card" style={{ marginBottom: 16, borderColor: '#7bb5ff', background: '#f3f8ff' }}>
              <h3>错题重练指引</h3>
              <p>{replayNotice}</p>
              <button onClick={() => navigate('/mistakes?module=reading&questionType=reading_quiz')}>返回错题本</button>
            </div>
          )}
          <PageSection title="阅读文本输入">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="粘贴一段阅读文本进行同义替换、难度与长难句分析"
              rows={10}
              style={{ width: '100%' }}
            />
            <ToolbarRow>
              <button onClick={runAll} disabled={!text.trim()}>一键分析</button>
            </ToolbarRow>
          </PageSection>

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

          <div className="card" style={{ marginTop: 16 }} ref={quizCardRef}>
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
                {autoCollectSummary && (
                  <div style={{ marginBottom: 10 }}>
                    <p>
                      已自动收录词汇：{autoCollectSummary.imported}，跳过已存在：{autoCollectSummary.skipped_existing}
                    </p>
                    <button onClick={() => navigate('/vocabulary')}>
                      去词汇页直接开练语境复现
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3>阅读策略训练（略读/扫读）</h3>
            <p style={{ fontSize: 12, color: '#666' }}>skim：主旨提炼 | scan：定位信息 | mixed：组合训练</p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
              <label>
                模式
                <select
                  value={strategyConfig.mode}
                  onChange={(e) => setStrategyConfig((prev) => ({ ...prev, mode: e.target.value }))}
                  style={{ marginLeft: 6 }}
                >
                  <option value="skim">skim</option>
                  <option value="scan">scan</option>
                  <option value="mixed">mixed</option>
                </select>
              </label>
              <label>
                题数
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={strategyConfig.count}
                  onChange={(e) => setStrategyConfig((prev) => ({ ...prev, count: e.target.value }))}
                  style={{ marginLeft: 6, width: 80 }}
                />
              </label>
              <label>
                难度
                <select
                  value={strategyConfig.difficulty}
                  onChange={(e) => setStrategyConfig((prev) => ({ ...prev, difficulty: e.target.value }))}
                  style={{ marginLeft: 6 }}
                >
                  <option value="">全部</option>
                  <option value="basic">basic</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
              </label>
              <button onClick={handleGenerateStrategy}>生成策略训练</button>
            </div>

            {strategySession?.questions?.length > 0 && (
              <div>
                {(strategySession.questions || []).map((q, idx) => (
                  <div key={q.id} style={{ border: '1px solid #eee', borderRadius: 8, padding: 10, marginBottom: 10 }}>
                    <p style={{ marginBottom: 6 }}>
                      {idx + 1}. [{q.mode}] {q.title} | 限时 {q.time_limit_seconds}s
                    </p>
                    <p style={{ marginBottom: 8 }}>{q.prompt}</p>
                    <p style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>{q.passage}</p>
                    {q.hint && <p style={{ fontSize: 12, color: '#666' }}>提示：{q.hint}</p>}
                    <input
                      type="text"
                      value={strategyAnswers[q.id] || ''}
                      onChange={(e) => setStrategyAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder="输入你的答案"
                      style={{ width: '100%', marginTop: 6, marginBottom: 6 }}
                    />
                    <label style={{ fontSize: 12 }}>
                      用时(秒)
                      <input
                        type="number"
                        min={0}
                        value={strategySpent[q.id] || ''}
                        onChange={(e) => setStrategySpent((prev) => ({ ...prev, [q.id]: e.target.value }))}
                        placeholder="不填则自动按页面停留时间估算"
                        style={{ marginLeft: 6, width: 130 }}
                      />
                    </label>
                  </div>
                ))}
                <button onClick={handleSubmitStrategy}>提交策略训练</button>
              </div>
            )}

            {strategyResult && (
              <div style={{ marginTop: 12 }}>
                <h4>策略训练结果</h4>
                <p>
                  正确率: {strategyResult.correct}/{strategyResult.total}
                  {' '}({Math.round((strategyResult.accuracy || 0) * 100)}%) |
                  限时完成率：{Math.round((strategyResult.on_time_rate || 0) * 100)}%
                </p>
                <p>建议：{strategyResult.recommended_focus}</p>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th align="left">question_id</th>
                      <th align="left">模式</th>
                      <th align="left">结果</th>
                      <th align="left">限时</th>
                      <th align="left">得分</th>
                      <th align="left">答案</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(strategyResult.details || []).map((d) => (
                      <tr key={d.question_id}>
                        <td>{d.question_id}</td>
                        <td>{d.mode}</td>
                        <td>{d.is_correct ? '✅' : '❌'}</td>
                        <td>{d.spent_seconds}/{d.time_limit_seconds}s {d.is_on_time ? '✅' : '⏰'}</td>
                        <td>{d.score}</td>
                        <td>{d.user_answer || '-'}</td>
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

export default Reading;
