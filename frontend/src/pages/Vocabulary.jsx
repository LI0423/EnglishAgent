import { useEffect, useMemo, useRef, useState } from 'react';
import SidebarMenu from '../components/layout/SidebarMenu';
import {
  addVocabularyWord,
  autoCollectVocabulary,
  generateContextReplay,
  generateVocabularyTest,
  getContextReplayRetryQueue,
  getDueVocabulary,
  getVocabularyList,
  getVocabularyScenarios,
  getVocabularyStrategyInsights,
  getVocabularyStats,
  importVocabularyScenario,
  getPrioritizedWrongReviewQueue,
  normalizeUiError,
  reviewVocabularyWord,
  startVocabularySession,
  submitContextReplay,
  submitVocabularyTest,
} from '../utils/api';
import { MetricCard, MetricGrid, ToolbarRow } from '../components/layout/DesktopUI';

import TopNav from "../components/layout/TopNav";
const emptyWord = {
  word: '',
  definition: '',
  examples: '',
  pronunciation: '',
  part_of_speech: '',
  source_module: 'manual',
  module_tag: 'general',
  topic_tags: '',
};

const moduleTagOptions = ['general', 'listening', 'reading', 'writing', 'speaking'];
const sourceOptions = ['manual', 'scenario_pack', 'auto_collect', 'reading', 'listening', 'writing', 'speaking'];
const metaIgnoreTags = new Set(['scenario', 'manual']);
const sourceLabelMap = {
  manual: '手动添加',
  scenario_pack: '场景词包',
  auto_collect: '自动收词',
  reading: '阅读',
  listening: '听力',
  writing: '写作',
  speaking: '口语',
};
const moduleLabelMap = {
  general: '通用',
  listening: '听力',
  reading: '阅读',
  writing: '写作',
  speaking: '口语',
};
const topicLabelMap = {
  accommodation: '住宿',
  education: '教育',
  environment: '环境',
  technology: '科技',
  health: '健康',
  economy: '经济',
  culture: '文化',
  transport: '交通',
  tourism: '旅游',
  work: '工作',
  career: '职业',
  family: '家庭',
  food: '饮食',
  media: '媒体',
  crime: '犯罪',
  government: '政府',
  housing: '住房',
};
const topicAliasToCanonical = {
  住宿: 'accommodation',
  教育: 'education',
  环境: 'environment',
  科技: 'technology',
  技术: 'technology',
  健康: 'health',
  经济: 'economy',
  文化: 'culture',
  交通: 'transport',
  旅游: 'tourism',
  工作: 'work',
  职业: 'career',
  家庭: 'family',
  饮食: 'food',
  食物: 'food',
  媒体: 'media',
  犯罪: 'crime',
  政府: 'government',
  住房: 'housing',
};

const sourceLabel = (value) => sourceLabelMap[value] || value;
const moduleLabel = (value) => moduleLabelMap[value] || value;
const topicLabel = (value) => topicLabelMap[value] || String(value || '').replace(/_/g, ' ');
const canonicalTopic = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const byAlias = topicAliasToCanonical[raw];
  if (byAlias) return byAlias;
  return normalizeTagToken(raw);
};

const normalizeTagToken = (value) => String(value || '').trim().toLowerCase();
const splitTagInput = (value) => String(value || '')
  .split(',')
  .map((x) => canonicalTopic(x))
  .filter(Boolean);

const parseWordMeta = (wordRow) => {
  const rawTags = Array.isArray(wordRow?.tags) ? wordRow.tags : [];
  const tags = rawTags.map((t) => normalizeTagToken(t)).filter(Boolean);
  const source = normalizeTagToken(wordRow?.source_module || 'manual') || 'manual';
  let module = 'general';
  const topics = [];

  tags.forEach((tag) => {
    if (tag.startsWith('module:')) {
      const value = normalizeTagToken(tag.slice(7));
      if (value) module = value;
      return;
    }
    if (tag.startsWith('topic:')) {
      const value = canonicalTopic(tag.slice(6));
      if (value) topics.push(value);
      return;
    }
    if (moduleTagOptions.includes(tag)) {
      module = tag;
      return;
    }
    if (!metaIgnoreTags.has(tag) && !sourceOptions.includes(tag)) {
      topics.push(canonicalTopic(tag));
    }
  });

  const uniqTopics = Array.from(new Set(topics));
  const chips = [
    `来源:${sourceLabel(source)}`,
    `模块:${moduleLabel(module)}`,
    ...uniqTopics.map((x) => `主题:${topicLabel(x)}`),
  ];
  return { source, module, topics: uniqTopics, chips };
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

  const [words, setWords] = useState([]);
  const [dueWords, setDueWords] = useState([]);
  const [stats, setStats] = useState({ total: 0, due_count: 0, avg_mastery: 0, by_source_module: {} });
  const [wordForm, setWordForm] = useState(emptyWord);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [todayReviewed, setTodayReviewed] = useState(0);
  const [learnStrategy, setLearnStrategy] = useState('spaced');
  const [strategyInsights, setStrategyInsights] = useState([]);

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
  const [successMessage, setSuccessMessage] = useState('');

  const [scenarios, setScenarios] = useState([]);
  const [scenarioModule, setScenarioModule] = useState('');
  const [scenarioTopic, setScenarioTopic] = useState('');

  const [collectText, setCollectText] = useState('');
  const [collectSource, setCollectSource] = useState('reading');
  const [collectTopic, setCollectTopic] = useState('general');
  const [listKeyword, setListKeyword] = useState('');
  const [listSourceModule, setListSourceModule] = useState('');
  const [listModuleTag, setListModuleTag] = useState('');
  const [listTopicTag, setListTopicTag] = useState('');

  const [contextMode, setContextMode] = useState('cloze');
  const [contextCount, setContextCount] = useState(5);
  const [contextData, setContextData] = useState(null);
  const [contextAnswers, setContextAnswers] = useState({});
  const [contextResult, setContextResult] = useState(null);
  const [contextRetryQueue, setContextRetryQueue] = useState([]);
  const [nextContextReplay, setNextContextReplay] = useState(null);
  const [prefillContextReady, setPrefillContextReady] = useState(false);
  const contextReplayCardRef = useRef(null);
  const contextSubmitBtnRef = useRef(null);
  const contextInputRefs = useRef({});
  const contextOptionRefs = useRef({});
  const successTimerRef = useRef(null);

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

  const clearSuccess = () => {
    if (successTimerRef.current) {
      window.clearTimeout(successTimerRef.current);
      successTimerRef.current = null;
    }
    setSuccessMessage('');
  };

  const showSuccess = (message, durationMs = 3500) => {
    if (successTimerRef.current) {
      window.clearTimeout(successTimerRef.current);
      successTimerRef.current = null;
    }
    setSuccessMessage(message);
    if (durationMs > 0) {
      successTimerRef.current = window.setTimeout(() => {
        setSuccessMessage('');
        successTimerRef.current = null;
      }, durationMs);
    }
  };

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
        getVocabularyList(300, {
          sourceModule: listSourceModule || null,
          tag: null,
          keyword: listKeyword || null,
        }),
        getDueVocabulary(100),
        getVocabularyStats(),
      ]);
      let filteredRows = rows || [];
      if (listModuleTag) {
        filteredRows = filteredRows.filter((w) => parseWordMeta(w).module === listModuleTag);
      }
      if (listTopicTag) {
        filteredRows = filteredRows.filter((w) => parseWordMeta(w).topics.includes(listTopicTag));
      }
      setWords(filteredRows);
      setDueWords(dueRows || []);
      setStats(statRows || { total: 0, due_count: 0, avg_mastery: 0, by_source_module: {} });
      const insightRows = await getVocabularyStrategyInsights(14);
      setStrategyInsights(insightRows || []);
      if (reviewMode === 'due') {
        setReviewQueue(dueRows || []);
      }
    } catch (e) {
      setError(normalizeUiError(e, '加载词汇数据失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWords();
  }, [listKeyword, listSourceModule, listModuleTag, listTopicTag]);

  useEffect(() => {
    loadWrongPriorityQueue().catch(() => {
      setWrongPriorityQueue([]);
    });
  }, [wrongWordIds]);

  const loadScenarios = async () => {
    try {
      const data = await getVocabularyScenarios(scenarioModule || null, scenarioTopic || null);
      setScenarios(data || []);
    } catch (err) {
      setError(typeof err === 'string' ? err : '加载场景词包失败');
      setScenarios([]);
    }
  };

  const loadContextRetryQueue = async () => {
    try {
      const rows = await getContextReplayRetryQueue(50);
      setContextRetryQueue(rows || []);
    } catch {
      setContextRetryQueue([]);
    }
  };

  useEffect(() => {
    loadScenarios();
  }, [scenarioModule, scenarioTopic]);

  useEffect(() => {
    loadContextRetryQueue();
  }, [words]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem('vocab_context_replay_prefill');
      if (!raw) return;
      const replay = JSON.parse(raw);
      if (replay && replay.session_id && Array.isArray(replay.questions)) {
        setContextData(replay);
        setContextAnswers({});
        setContextResult(null);
        showSuccess(`已为你自动准备语境复现题（${replay.questions.length}题）`, 4200);
        setPrefillContextReady(true);
      }
      localStorage.removeItem('vocab_context_replay_prefill');
    } catch {
      localStorage.removeItem('vocab_context_replay_prefill');
    }
  }, []);

  useEffect(() => {
    if (!prefillContextReady) return;
    const timer = window.setTimeout(() => {
      contextReplayCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    const clear = window.setTimeout(() => setPrefillContextReady(false), 3200);
    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(clear);
    };
  }, [prefillContextReady]);

  useEffect(() => {
    return () => {
      if (successTimerRef.current) {
        window.clearTimeout(successTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!contextData?.questions?.length) return;
    const firstPendingQuestion = (contextData.questions || []).find((q) => {
      const answer = contextAnswers[q.id];
      if (q.answer_format === 'text') {
        return !answer || !String(answer).trim();
      }
      return !answer;
    });
    if (!firstPendingQuestion) return;
    const el = firstPendingQuestion.answer_format === 'text'
      ? contextInputRefs.current[firstPendingQuestion.id]
      : contextOptionRefs.current[firstPendingQuestion.id];
    if (!el) return;
    const timer = window.setTimeout(() => {
      el.focus();
      if (firstPendingQuestion.answer_format === 'text') {
        el.select?.();
      }
    }, 60);
    return () => window.clearTimeout(timer);
  }, [contextData, contextResult]);

  const focusNextContextInput = (currentQuestionId) => {
    const questions = contextData?.questions || [];
    const idx = questions.findIndex((q) => q.id === currentQuestionId);
    if (idx < 0) return;
    for (let i = idx + 1; i < questions.length; i += 1) {
      const q = questions[i];
      const el = q.answer_format === 'text'
        ? contextInputRefs.current[q.id]
        : contextOptionRefs.current[q.id];
      if (el) {
        el.focus();
        if (q.answer_format === 'text') {
          el.select?.();
        }
        return;
      }
    }
    contextSubmitBtnRef.current?.focus();
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    try {
      setError('');
      clearSuccess();
      await addVocabularyWord({
        ...(() => {
          const { module_tag, topic_tags, ...rest } = wordForm;
          const topics = splitTagInput(topic_tags);
          const tags = [];
          if (module_tag) tags.push(`module:${module_tag}`);
          topics.forEach((x) => tags.push(`topic:${x}`));
          return {
            ...rest,
            examples: wordForm.examples ? wordForm.examples.split('|').map((x) => x.trim()).filter(Boolean) : [],
            tags,
          };
        })(),
      });
      setWordForm(emptyWord);
      showSuccess('词汇已添加');
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
      setLearnStrategy(session?.strategy || strategy);
      setLearnSession(session.words || []);
      const insightRows = await getVocabularyStrategyInsights(14);
      setStrategyInsights(insightRows || []);
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
    <div className="home-page web-dashboard vocab-page">
      <TopNav />

      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>

        <div className="content-area content-shell vocab-page">
        <div className="web-page-head">
          <div>
            <h2>词汇学习</h2>
            <p>新词学习、复习巩固、场景词包与测试统一管理。</p>
          </div>
          <div className="web-page-head-actions">
            <button className="vocab-btn vocab-btn-secondary" onClick={loadWords}>刷新词汇</button>
          </div>
        </div>
        <div className="card vocab-card">
          <h3>今日概览</h3>
          <MetricGrid className="vocab-overview-grid">
            <MetricCard label="词汇总数" value={stats.total || 0} />
            <MetricCard label="到期复习" value={stats.due_count || 0} />
            <MetricCard label="平均掌握度" value={`${Math.round((stats.avg_mastery || 0) * 100)}%`} />
            <MetricCard label="今日已练" value={todayReviewed} />
            <MetricCard label="错词待复习" value={wrongWords.length} />
          </MetricGrid>
        </div>

        <div className="card vocab-card">
          <h3>新词学习（Learn）</h3>
          <ToolbarRow className="vocab-actions-row">
            <button className="vocab-btn vocab-btn-primary" onClick={() => onStartSession('spaced')}>开始10词（Spaced）</button>
            <button className="vocab-btn vocab-btn-primary" onClick={() => onStartSession('root')}>开始10词（词根词缀）</button>
            <button className="vocab-btn vocab-btn-primary" onClick={() => onStartSession('context')}>开始10词（语境优先）</button>
            <button className="vocab-btn vocab-btn-primary" onClick={() => onStartSession('mixed')}>开始10词（混合调度）</button>
          </ToolbarRow>
          {strategyInsights.length > 0 && (
            <p style={{ marginTop: 8, fontSize: 13, color: '#4a5568' }}>
              近14天策略会话：{strategyInsights.map((x) => `${x.strategy}(${x.session_count})`).join(' / ')}
            </p>
          )}
          {learning && currentLearnWord && (
            <div className="vocab-focus-panel">
              <p>进度：{learnIndex + 1}/{learnSession.length} · 策略：{learnStrategy}</p>
              <p>
                调度分：{Number(currentLearnWord.scheduler_score || 0).toFixed(3)}
                {' · '}
                {currentLearnWord.scheduler_reason || '综合调度'}
              </p>
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
          <h3>场景词汇包</h3>
          <div className="vocab-actions-row">
            <select value={scenarioModule} onChange={(e) => setScenarioModule(e.target.value)}>
              <option value="">全部模块</option>
              <option value="listening">listening</option>
              <option value="reading">reading</option>
              <option value="writing">writing</option>
              <option value="speaking">speaking</option>
            </select>
            <input
              placeholder="topic (如 environment)"
              value={scenarioTopic}
              onChange={(e) => setScenarioTopic(e.target.value)}
              style={{ width: 220 }}
            />
            <button className="vocab-btn vocab-btn-secondary" onClick={loadScenarios}>刷新词包</button>
          </div>
          <div className="vocab-test-list">
            {(scenarios || []).map((pack) => (
              <div key={`${pack.module}_${pack.topic}`} className="vocab-test-item">
                <p>
                  <strong>{pack.module}/{pack.topic}</strong> · level: {pack.level} ·
                  学习进度: {pack.learned_count}/{pack.total_count}
                </p>
                <p style={{ opacity: 0.9 }}>
                  {(pack.words || []).slice(0, 4).map((w) => w.word).join(', ')}
                </p>
                <button
                  className="vocab-btn vocab-btn-primary"
                  onClick={async () => {
                    try {
                      setError('');
                      const result = await importVocabularyScenario(pack.module, pack.topic, 20);
                      showSuccess(`已导入 ${result.imported} 词，跳过 ${result.skipped_existing} 词`);
                      await Promise.all([loadWords(), loadScenarios()]);
                    } catch (err) {
                      setError(typeof err === 'string' ? err : '导入场景词包失败');
                    }
                  }}
                >
                  导入到我的词汇本
                </button>
              </div>
            ))}
            {scenarios.length === 0 && <p>暂无场景词包数据</p>}
          </div>
        </div>

        <div className="card vocab-card">
          <h3>文本自动收词（阅读/听力）</h3>
          <div className="vocab-actions-row">
            <select value={collectSource} onChange={(e) => setCollectSource(e.target.value)}>
              <option value="reading">reading</option>
              <option value="listening">listening</option>
              <option value="writing">writing</option>
              <option value="speaking">speaking</option>
            </select>
            <input
              placeholder="topic"
              value={collectTopic}
              onChange={(e) => setCollectTopic(e.target.value)}
              style={{ width: 180 }}
            />
          </div>
          <textarea
            rows={4}
            value={collectText}
            onChange={(e) => setCollectText(e.target.value)}
            placeholder="粘贴英文段落，自动抽取候选生词并收录到词汇本"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <button
            className="vocab-btn vocab-btn-primary"
            disabled={!collectText.trim()}
            onClick={async () => {
              try {
                setError('');
                const result = await autoCollectVocabulary(collectText, collectSource, collectTopic, 20);
                showSuccess(`自动收录 ${result.imported} 词，跳过 ${result.skipped_existing} 词`);
                await loadWords();
              } catch (err) {
                setError(typeof err === 'string' ? err : '自动收词失败');
              }
            }}
          >
            自动收录
          </button>
        </div>

        <div
          ref={contextReplayCardRef}
          className={`card vocab-card${prefillContextReady ? ' vocab-card-highlight' : ''}`}
        >
          <h3>语境复现训练（Context Replay）</h3>
          <div className="vocab-actions-row">
            <select value={contextMode} onChange={(e) => setContextMode(e.target.value)}>
              <option value="cloze">cloze</option>
              <option value="multiple_choice">multiple_choice</option>
            </select>
            <input
              type="number"
              min="1"
              max="20"
              value={contextCount}
              onChange={(e) => setContextCount(e.target.value)}
              style={{ width: 90 }}
            />
            <button
              className="vocab-btn vocab-btn-primary"
              onClick={async () => {
                try {
                  setError('');
                  clearSuccess();
                  const data = await generateContextReplay({
                    count: Number(contextCount) || 5,
                    sourceModule: listSourceModule || null,
                    topic: listTopicTag || null,
                    mode: contextMode,
                  });
                  setContextData(data);
                  setContextAnswers({});
                  setContextResult(null);
                } catch (err) {
                  setError(typeof err === 'string' ? err : '生成语境复现题失败');
                }
              }}
            >
              生成语境题
            </button>
            <button
              className="vocab-btn vocab-btn-primary"
              disabled={!contextData?.session_id}
              ref={contextSubmitBtnRef}
              onClick={async () => {
                try {
                  setError('');
                  const answers = (contextData.questions || []).map((q) => ({
                    question_id: q.id,
                    answer: String(contextAnswers[q.id] || ''),
                  }));
                  const result = await submitContextReplay(contextData.session_id, answers);
                  setContextResult(result);
                  showSuccess(`语境复现完成：${result.correct}/${result.total}`);
                  const wrongWordIds = Array.from(
                    new Set(
                      (result.details || [])
                        .filter((d) => !d.is_correct && d.word_id)
                        .map((d) => String(d.word_id)),
                    ),
                  );
                  if (wrongWordIds.length > 0) {
                    try {
                      const replay = await generateContextReplay({
                        count: Math.min(8, wrongWordIds.length),
                        mode: contextMode,
                        wordIds: wrongWordIds,
                      });
                      if (replay?.session_id && Array.isArray(replay.questions)) {
                        setNextContextReplay(replay);
                        showSuccess(
                          `语境复现完成：${result.correct}/${result.total}，已自动准备下一组强化题（${replay.questions.length}题）`,
                          5000,
                        );
                      } else {
                        setNextContextReplay(null);
                      }
                    } catch {
                      setNextContextReplay(null);
                    }
                  } else {
                    setNextContextReplay(null);
                  }
                  await Promise.all([loadWords(), loadContextRetryQueue()]);
                } catch (err) {
                  setError(typeof err === 'string' ? err : '提交语境复现失败');
                }
              }}
            >
              提交语境题
            </button>
          </div>
          {contextData && (
            <div className="vocab-test-list">
              {(contextData.questions || []).map((q, idx) => (
                <div key={q.id} className="vocab-test-item">
                  <p style={{ marginBottom: 6 }}>{idx + 1}. {q.prompt}</p>
                  {q.hint && <p style={{ opacity: 0.7 }}>Hint: {q.hint}</p>}
                  {Array.isArray(q.options) && q.options.length > 0 ? (
                    <div style={{ display: 'grid', gap: 4 }}>
                      {q.options.map((opt, optionIndex) => (
                        <label key={opt}>
                          <input
                            type="radio"
                            name={`ctx_${q.id}`}
                            ref={(el) => {
                              if (el && optionIndex === 0) contextOptionRefs.current[q.id] = el;
                            }}
                            checked={contextAnswers[q.id] === opt}
                            onChange={() => setContextAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                            onKeyDown={(e) => {
                              if (e.key !== 'Enter') return;
                              e.preventDefault();
                              if (contextAnswers[q.id] !== opt) {
                                setContextAnswers((prev) => ({ ...prev, [q.id]: opt }));
                              }
                              window.setTimeout(() => focusNextContextInput(q.id), 0);
                            }}
                          />
                          {opt}
                        </label>
                      ))}
                    </div>
                  ) : (
                    <input
                      ref={(el) => {
                        if (el) contextInputRefs.current[q.id] = el;
                      }}
                      value={contextAnswers[q.id] || ''}
                      onChange={(e) => setContextAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      onKeyDown={(e) => {
                        if (e.key !== 'Enter') return;
                        e.preventDefault();
                        focusNextContextInput(q.id);
                      }}
                      placeholder="填入你认为最合适的词"
                    />
                  )}
                </div>
              ))}
            </div>
          )}
          {contextData && (
            <p style={{ fontSize: 12, opacity: 0.8, marginTop: 6 }}>
              快捷操作：填空题与多选题都可按 Enter 自动跳到下一题，最后定位到“提交语境题”。
            </p>
          )}
          {contextResult && (
            <div style={{ marginTop: 10 }}>
              <p>得分：{contextResult.correct}/{contextResult.total}（accuracy: {contextResult.accuracy}）</p>
              <ul>
                {(contextResult.details || []).map((d) => (
                  <li key={d.question_id}>
                    {d.is_correct ? '✅' : `❌（你的答案: ${d.user_answer}，正确: ${d.expected_answer}）`}
                    {d.explanation ? ` ｜ ${d.explanation}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {nextContextReplay && (
            <div className="vocab-subpanel" style={{ marginTop: 10 }}>
              <h4 style={{ marginBottom: 8 }}>下一组强化题已就绪</h4>
              <p style={{ marginBottom: 8 }}>
                已基于本轮错词自动生成 {nextContextReplay.questions?.length || 0} 题。
              </p>
              <button
                className="vocab-btn vocab-btn-primary"
                onClick={() => {
                  setContextData(nextContextReplay);
                  setContextAnswers({});
                  setContextResult(null);
                  setNextContextReplay(null);
                  showSuccess('已切换到下一组强化题');
                }}
              >
                开始下一组强化题
              </button>
            </div>
          )}
          <div className="vocab-subpanel" style={{ marginTop: 12 }}>
            <h4 style={{ marginBottom: 8 }}>错题二次强化队列</h4>
            <div className="vocab-actions-row">
              <button className="vocab-btn vocab-btn-secondary" onClick={loadContextRetryQueue}>刷新队列</button>
              <button
                className="vocab-btn vocab-btn-primary"
                disabled={contextRetryQueue.length === 0}
                onClick={async () => {
                  try {
                    setError('');
                    const topIds = contextRetryQueue.slice(0, 8).map((x) => x.word_id);
                    const data = await generateContextReplay({
                      count: Math.min(8, topIds.length),
                      mode: contextMode,
                      wordIds: topIds,
                    });
                    setContextData(data);
                    setContextAnswers({});
                    setContextResult(null);
                    showSuccess(`已生成错题强化训练（${topIds.length}词）`);
                  } catch (err) {
                    setError(typeof err === 'string' ? err : '生成错题强化训练失败');
                  }
                }}
              >
                一键重练 Top8
              </button>
            </div>
            {contextRetryQueue.length > 0 ? (
              <div className="vocab-table-wrap">
                <table className="vocab-table">
                  <thead>
                    <tr>
                      <th align="left">单词</th>
                      <th align="left">错题次数</th>
                      <th align="left">优先级</th>
                      <th align="left">原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contextRetryQueue.slice(0, 8).map((item) => (
                      <tr key={item.word_id}>
                        <td>{item.word}</td>
                        <td>{item.wrong_count}</td>
                        <td>{Number(item.priority_score || 0).toFixed(3)}</td>
                        <td>{item.priority_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p>暂无语境复现错题。</p>
            )}
          </div>
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
            <select value={wordForm.source_module} onChange={(e) => setWordForm({ ...wordForm, source_module: e.target.value })}>
              {sourceOptions.map((x) => <option key={x} value={x}>{sourceLabel(x)}</option>)}
            </select>
            <select value={wordForm.module_tag} onChange={(e) => setWordForm({ ...wordForm, module_tag: e.target.value })}>
              {moduleTagOptions.map((x) => <option key={x} value={x}>{moduleLabel(x)}</option>)}
            </select>
            <input
              placeholder="topic 标签（逗号分隔，如 accommodation,education）"
              value={wordForm.topic_tags}
              onChange={(e) => setWordForm({ ...wordForm, topic_tags: e.target.value })}
            />
            <button className="vocab-btn vocab-btn-primary" type="submit">添加词汇</button>
          </form>
        </div>

        <div className="card vocab-card">
          <h3>词汇本</h3>
          <div className="vocab-actions-row">
            <input
              placeholder="关键词搜索（word/definition）"
              value={listKeyword}
              onChange={(e) => setListKeyword(e.target.value)}
              style={{ width: 260 }}
            />
            <select value={listSourceModule} onChange={(e) => setListSourceModule(e.target.value)}>
              <option value="">全部来源</option>
              {sourceOptions.map((x) => <option key={x} value={x}>{sourceLabel(x)}</option>)}
            </select>
            <select value={listModuleTag} onChange={(e) => setListModuleTag(e.target.value)}>
              <option value="">全部模块</option>
              {moduleTagOptions.map((x) => <option key={x} value={x}>{moduleLabel(x)}</option>)}
            </select>
            <select value={listTopicTag} onChange={(e) => setListTopicTag(e.target.value)}>
              <option value="">全部主题</option>
              {Array.from(new Set(words.flatMap((w) => parseWordMeta(w).topics))).sort().map((topic) => (
                <option key={topic} value={topic}>{topicLabel(topic)}</option>
              ))}
            </select>
            <button className="vocab-btn vocab-btn-secondary" onClick={loadWords}>刷新</button>
          </div>
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
                    <td>
                      <div className="vocab-chip-wrap">
                        {parseWordMeta(w).chips.map((chip) => (
                          <span key={`${w.id}_${chip}`} className="vocab-chip">{chip}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
                {words.length === 0 && (
                  <tr><td colSpan={4}>暂无词汇数据</td></tr>
                )}
              </tbody>
            </table>
            </div>
          )}
          {successMessage && <p className="vocab-status vocab-status-success">{successMessage}</p>}
          {error && <p className="vocab-status vocab-status-error">{error}</p>}
        </div>
      </div>
      </div>
    </div>
  );
}

export default Vocabulary;
