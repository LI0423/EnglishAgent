import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  autoCollectVocabulary,
  generateListeningMaterial,
  generateListeningIntensive,
  generateContextReplay,
  generateListeningQuiz,
  getListeningSegment,
  getListeningLibrary,
  getListeningLibraryVersion,
  getListeningQuizVersion,
  getListeningTTSHealth,
  getListeningStatus,
  normalizeUiError,
  pauseListening,
  renderListeningTTS,
  resumeListening,
  setListeningSpeed,
  startListening,
  stopListening,
  submitListeningIntensive,
  submitListeningQuiz,
} from '../utils/api';
import { MetricCard, MetricGrid, PageSection, ToolbarRow } from '../components/layout/DesktopUI';
import SidebarMenu from '../components/layout/SidebarMenu';

import TopNav from "../components/layout/TopNav";
const API_BASE = String(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');

function Listening() {
  const navigate = useNavigate();
  const location = useLocation();

  const [library, setLibrary] = useState([]);
  const [libraryVersion, setLibraryVersion] = useState(null);
  const [quizVersion, setQuizVersion] = useState(null);
  const [status, setStatus] = useState({});
  const [quizConfig, setQuizConfig] = useState({ count: 3, difficulty: '' });
  const [quiz, setQuiz] = useState(null);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizResult, setQuizResult] = useState(null);
  const [intensiveConfig, setIntensiveConfig] = useState({ count: 4, difficulty: '', mode: 'mixed' });
  const [intensiveSession, setIntensiveSession] = useState(null);
  const [intensiveAnswers, setIntensiveAnswers] = useState({});
  const [intensiveResult, setIntensiveResult] = useState(null);
  const [segmentPreview, setSegmentPreview] = useState(null);
  const [autoCollectSummary, setAutoCollectSummary] = useState(null);
  const [replayNotice, setReplayNotice] = useState('');
  const [ttsHealth, setTtsHealth] = useState(null);
  const [ttsForm, setTtsForm] = useState({
    title: 'Room B lecture notice',
    text: 'The lecture starts at nine thirty in Room B.',
    difficulty: 'easy',
    lang: 'en',
    voice: 'M1',
    speed: 1.0,
  });
  const [ttsAudioUrl, setTtsAudioUrl] = useState('');
  const [ttsLoading, setTtsLoading] = useState(false);
  const [materialSaving, setMaterialSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const quizCardRef = useRef(null);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [lib, st, lv, qv, ttsMeta] = await Promise.all([
        getListeningLibrary(),
        getListeningStatus(),
        getListeningLibraryVersion(),
        getListeningQuizVersion(),
        getListeningTTSHealth(),
      ]);
      setLibrary(lib || []);
      setStatus(st || {});
      setLibraryVersion(lv || null);
      setQuizVersion(qv || null);
      setTtsHealth(ttsMeta || null);
    } catch (e) {
      setError(normalizeUiError(e, '加载听力数据失败'));
    } finally {
      setLoading(false);
    }
  };

  const toAudioSrc = (url) => {
    const raw = String(url || '').trim();
    if (!raw) return '';
    if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
    if (raw.startsWith('/')) return `${API_BASE}${raw}`;
    return `${API_BASE}/${raw}`;
  };

  const handleRenderTTS = async () => {
    if (!String(ttsForm.text || '').trim()) {
      setError('请输入要播报的文本');
      return;
    }
    setTtsLoading(true);
    setError('');
    try {
      const data = await renderListeningTTS({
        text: ttsForm.text,
        lang: ttsForm.lang,
        voice: ttsForm.voice,
        speed: Number(ttsForm.speed) || 1.0,
      });
      setTtsAudioUrl(toAudioSrc(data?.audio_url));
    } catch (e) {
      setError(typeof e === 'string' ? e : 'TTS 生成失败');
    } finally {
      setTtsLoading(false);
    }
  };

  const handleGenerateMaterial = async () => {
    if (!String(ttsForm.title || '').trim()) {
      setError('请输入素材标题');
      return;
    }
    if (!String(ttsForm.text || '').trim()) {
      setError('请输入素材文本');
      return;
    }
    setMaterialSaving(true);
    setError('');
    try {
      const data = await generateListeningMaterial({
        title: ttsForm.title,
        transcript: ttsForm.text,
        difficulty: ttsForm.difficulty,
        lang: ttsForm.lang,
        voice: ttsForm.voice,
        speed: Number(ttsForm.speed) || 1.0,
      });
      setTtsAudioUrl(toAudioSrc(data?.audio?.url));
      await loadData();
    } catch (e) {
      setError(typeof e === 'string' ? e : '保存听力素材失败');
    } finally {
      setMaterialSaving(false);
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
    setAutoCollectSummary(null);
    try {
      const answers = (quiz.questions || []).map((q) => ({
        question_id: q.id,
        answer: quizAnswers[q.id] || '',
      }));
      const result = await submitListeningQuiz(quiz.quiz_id, answers);
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
        const collectRes = await autoCollectVocabulary(corpus, 'listening', 'quiz_wrong', 20);
        setAutoCollectSummary(collectRes || null);
        const wordIds = Array.isArray(collectRes?.word_ids) ? collectRes.word_ids.filter(Boolean) : [];
        if (wordIds.length > 0) {
          const replay = await generateContextReplay({
            count: Math.min(8, wordIds.length),
            sourceModule: 'listening',
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
      setError(typeof e === 'string' ? e : '提交测验失败');
    }
  };

  const handleGenerateIntensive = async () => {
    setError('');
    setIntensiveResult(null);
    setSegmentPreview(null);
    try {
      const data = await generateListeningIntensive({
        count: Number(intensiveConfig.count) || 4,
        difficulty: intensiveConfig.difficulty || null,
        mode: intensiveConfig.mode || 'mixed',
      });
      setIntensiveSession(data || null);
      setIntensiveAnswers({});
      const first = (data?.questions || [])[0];
      if (first?.audio_id) {
        const preview = await getListeningSegment(first.audio_id, first.start_time || 0, first.end_time || 20);
        setSegmentPreview(preview || null);
      }
    } catch (e) {
      setError(typeof e === 'string' ? e : '生成精听训练失败');
    }
  };

  const handleSubmitIntensive = async () => {
    if (!intensiveSession?.session_id) return;
    setError('');
    try {
      const answers = (intensiveSession.questions || []).map((q) => ({
        question_id: q.id,
        answer: intensiveAnswers[q.id] || '',
      }));
      const result = await submitListeningIntensive(intensiveSession.session_id, answers);
      setIntensiveResult(result || null);
    } catch (e) {
      setError(typeof e === 'string' ? e : '提交精听训练失败');
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search || '');
    if (params.get('replay') !== '1') return;
    const questionId = params.get('questionId') || '';
    setReplayNotice(questionId ? `来自错题重练：题目 ${questionId}` : '来自错题重练：请优先完成一次听力测验');
    const timer = window.setTimeout(() => {
      quizCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(timer);
  }, [location.search]);

  return (
    <div className="home-page web-dashboard listening-page">
      <TopNav />
      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>

        <div className="content-area content-shell">
          <div className="web-page-head">
            <div>
              <h2>听力练习</h2>
              <p>听力素材、测验与精听训练统一在一个工作台完成。</p>
            </div>
            <div className="web-page-head-actions">
              <button className="plan-filter-btn" onClick={loadData}>刷新数据</button>
            </div>
          </div>
          {replayNotice && (
            <div className="card listening-notice">
              <h3>错题重练指引</h3>
              <p>{replayNotice}</p>
              <button className="plan-filter-btn" onClick={() => navigate('/mistakes?module=listening&questionType=listening_quiz')}>返回错题本</button>
            </div>
          )}
          <PageSection title="播放状态" className="listening-card listening-status-card">
            <MetricGrid className="listening-metric-grid">
              <MetricCard label="当前素材" value={status.audio_id || '无'} />
              <MetricCard label="播放状态" value={status.is_playing ? '播放中' : '未播放'} />
              <MetricCard label="播放速度" value={`${status.speed || 1.0}x`} />
              <MetricCard label="素材库版本" value={libraryVersion?.version || '-'} />
              <MetricCard label="题库版本" value={quizVersion?.version || '-'} />
            </MetricGrid>
            <ToolbarRow className="listening-actions">
              <button className="plan-filter-btn" onClick={() => safeControl(() => pauseListening(status.current_time || 0))}>暂停</button>
              <button className="plan-filter-btn" onClick={() => safeControl(() => resumeListening(status.current_time || 0))}>继续</button>
              <button className="plan-filter-btn" onClick={() => safeControl(() => stopListening())}>停止</button>
              <button className="plan-filter-btn" onClick={() => safeControl(() => setListeningSpeed(0.8))}>0.8x</button>
              <button className="plan-filter-btn" onClick={() => safeControl(() => setListeningSpeed(1.0))}>1.0x</button>
              <button className="plan-filter-btn" onClick={() => safeControl(() => setListeningSpeed(1.25))}>1.25x</button>
              <button className="plan-filter-btn" onClick={loadData}>刷新</button>
            </ToolbarRow>
          </PageSection>

          <div className="card listening-card">
            <h3>Supertonic 听力播报（本地 TTS）</h3>
            <p className="listening-subtle">
              后端: {ttsHealth?.backend || '-'} | Supertonic 可用: {String(Boolean(ttsHealth?.supertonic_available))}
            </p>
            <div className="listening-form-grid">
              <input
                className="plan-input"
                value={ttsForm.title}
                onChange={(e) => setTtsForm((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="素材标题"
              />
              <textarea
                className="plan-input listening-textarea"
                value={ttsForm.text}
                onChange={(e) => setTtsForm((prev) => ({ ...prev, text: e.target.value }))}
                rows={3}
              />
              <div className="listening-actions">
                <select
                  className="plan-input"
                  value={ttsForm.difficulty}
                  onChange={(e) => setTtsForm((prev) => ({ ...prev, difficulty: e.target.value }))}
                >
                  <option value="easy">easy</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
                <input
                  className="plan-input listening-short-input"
                  value={ttsForm.lang}
                  onChange={(e) => setTtsForm((prev) => ({ ...prev, lang: e.target.value }))}
                  placeholder="lang: en"
                />
                <input
                  className="plan-input listening-short-input"
                  value={ttsForm.voice}
                  onChange={(e) => setTtsForm((prev) => ({ ...prev, voice: e.target.value }))}
                  placeholder="voice: M1"
                />
                <input
                  className="plan-input listening-short-input"
                  type="number"
                  min={0.7}
                  max={2}
                  step={0.1}
                  value={ttsForm.speed}
                  onChange={(e) => setTtsForm((prev) => ({ ...prev, speed: e.target.value }))}
                />
                <button className="plan-filter-btn" onClick={handleRenderTTS} disabled={ttsLoading}>{ttsLoading ? '生成中...' : '生成播报音频'}</button>
                <button className="plan-filter-btn" onClick={handleGenerateMaterial} disabled={materialSaving}>
                  {materialSaving ? '保存中...' : '生成并加入素材库'}
                </button>
              </div>
              {ttsAudioUrl && <audio className="listening-audio" controls src={ttsAudioUrl} />}
            </div>
          </div>

          <div className="card listening-card">
            <h3>听力素材库（最小可用）</h3>
            {loading ? <p>加载中...</p> : (
              <div className="listening-table-wrap">
              <table className="listening-table">
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
                        {item.url && (
                          <audio className="listening-row-audio" controls src={toAudioSrc(item.url)} />
                        )}
                        <button
                          className="plan-filter-btn"
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
              </div>
            )}
            {error && <p className="ts-error">{error}</p>}
          </div>

          <div className="card listening-card" ref={quizCardRef}>
            <h3>听力测验</h3>
            <div className="listening-actions">
              <label>
                题数
                <input
                  className="plan-input listening-number-input"
                  type="number"
                  min={1}
                  max={20}
                  value={quizConfig.count}
                  onChange={(e) => setQuizConfig((prev) => ({ ...prev, count: e.target.value }))}
                />
              </label>
              <label>
                难度
                <select
                  className="plan-input"
                  value={quizConfig.difficulty}
                  onChange={(e) => setQuizConfig((prev) => ({ ...prev, difficulty: e.target.value }))}
                >
                  <option value="">全部</option>
                  <option value="easy">easy</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
              </label>
              <button className="plan-filter-btn" onClick={handleGenerateQuiz}>生成测验</button>
            </div>

            {!quiz && <p>点击“生成测验”开始答题。</p>}
            {quiz?.questions?.length > 0 && (
              <div>
                {quiz.questions.map((q, idx) => (
                  <div key={q.id} className="listening-question-card">
                    <p className="listening-question-title">
                      {idx + 1}. {q.prompt}
                    </p>
                    <p className="listening-subtle">
                      audio: {q.audio_id} | difficulty: {q.difficulty}
                    </p>
                    {q.audio_url && <audio className="listening-audio" controls src={toAudioSrc(q.audio_url)} />}
                    <div className="listening-option-list">
                      {(q.options || []).map((opt) => (
                        <label key={`${q.id}-${opt}`}>
                          <input
                            type="radio"
                            name={`q-${q.id}`}
                            value={opt}
                            checked={quizAnswers[q.id] === opt}
                            onChange={(e) => setQuizAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                          />
                          {opt}
                        </label>
                      ))}
                      {!q.options && (
                        <input
                          className="plan-input"
                          type="text"
                          value={quizAnswers[q.id] || ''}
                          onChange={(e) => setQuizAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                          placeholder="输入答案"
                        />
                      )}
                    </div>
                  </div>
                ))}
                <button className="plan-filter-btn" onClick={handleSubmitQuiz}>提交测验</button>
              </div>
            )}

            {quizResult && (
              <div className="listening-result-block">
                <h4>测验结果</h4>
                <p>
                  正确率: {quizResult.correct}/{quizResult.total} ({Math.round((quizResult.accuracy || 0) * 100)}%)
                </p>
                <button
                  className="plan-filter-btn"
                  onClick={() => navigate('/mistakes?module=listening&questionType=listening_quiz')}
                >
                  查看本次听力错题
                </button>
                {autoCollectSummary && (
                  <div className="listening-inline-panel">
                    <p>
                      已自动收录词汇：{autoCollectSummary.imported}，跳过已存在：{autoCollectSummary.skipped_existing}
                    </p>
                    <button className="plan-filter-btn" onClick={() => navigate('/vocabulary')}>
                      去词汇页直接开练语境复现
                    </button>
                  </div>
                )}
                <div className="listening-table-wrap">
                <table className="listening-table">
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
              </div>
            )}
          </div>

          <div className="card listening-card">
            <h3>精听句段训练</h3>
            <p className="listening-subtle">模式：dictation（填空）/ keyword（关键词）/ mixed（混合）</p>
            <div className="listening-actions">
              <label>
                题数
                <input
                  className="plan-input listening-number-input"
                  type="number"
                  min={1}
                  max={20}
                  value={intensiveConfig.count}
                  onChange={(e) => setIntensiveConfig((prev) => ({ ...prev, count: e.target.value }))}
                />
              </label>
              <label>
                难度
                <select
                  className="plan-input"
                  value={intensiveConfig.difficulty}
                  onChange={(e) => setIntensiveConfig((prev) => ({ ...prev, difficulty: e.target.value }))}
                >
                  <option value="">全部</option>
                  <option value="easy">easy</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
              </label>
              <label>
                模式
                <select
                  className="plan-input"
                  value={intensiveConfig.mode}
                  onChange={(e) => setIntensiveConfig((prev) => ({ ...prev, mode: e.target.value }))}
                >
                  <option value="mixed">mixed</option>
                  <option value="dictation">dictation</option>
                  <option value="keyword">keyword</option>
                </select>
              </label>
              <button className="plan-filter-btn" onClick={handleGenerateIntensive}>生成精听训练</button>
            </div>

            {segmentPreview && (
              <div className="listening-inline-panel">
                <p>
                  句段预览：{segmentPreview.audio_id} | {segmentPreview.start_time}s - {segmentPreview.end_time}s
                </p>
                <p className="listening-subtle">建议先用 {status.speed || 1.0}x 播放，再切换慢速精听。</p>
              </div>
            )}

            {intensiveSession?.questions?.length > 0 && (
              <div>
                {(intensiveSession.questions || []).map((q, idx) => (
                  <div key={q.id} className="listening-question-card">
                    <p className="listening-question-title">{idx + 1}. {q.instruction}</p>
                    <p>{q.prompt}</p>
                    <p className="listening-subtle">
                      audio: {q.audio_id} | {q.start_time}s-{q.end_time}s | {q.question_type}
                    </p>
                    {q.audio_url && <audio className="listening-audio" controls src={toAudioSrc(q.audio_url)} />}
                    {q.hint && <p className="listening-subtle">提示：{q.hint}</p>}
                    <input
                      className="plan-input"
                      type="text"
                      value={intensiveAnswers[q.id] || ''}
                      onChange={(e) => setIntensiveAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder="输入你的答案"
                    />
                  </div>
                ))}
                <button className="plan-filter-btn" onClick={handleSubmitIntensive}>提交精听训练</button>
              </div>
            )}

            {intensiveResult && (
              <div className="listening-result-block">
                <h4>精听训练结果</h4>
                <p>
                  正确率: {intensiveResult.correct}/{intensiveResult.total}
                  {' '}({Math.round((intensiveResult.accuracy || 0) * 100)}%) |
                  建议速度：{intensiveResult.recommended_speed}x
                </p>
                <div className="listening-table-wrap">
                <table className="listening-table">
                  <thead>
                    <tr>
                      <th align="left">question_id</th>
                      <th align="left">结果</th>
                      <th align="left">得分</th>
                      <th align="left">你的答案</th>
                      <th align="left">标准答案</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(intensiveResult.details || []).map((d) => (
                      <tr key={d.question_id}>
                        <td>{d.question_id}</td>
                        <td>{d.is_correct ? '✅' : '❌'}</td>
                        <td>{d.score}</td>
                        <td>{d.user_answer || '-'}</td>
                        <td>{d.expected_answer || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Listening;
