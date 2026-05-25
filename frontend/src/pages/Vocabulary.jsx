import { useEffect, useMemo, useRef, useState } from 'react';
import SidebarMenu from '../components/layout/SidebarMenu';
import {
  addVocabularyWord,
  autoCollectVocabulary,
  generateContextReplay,
  generateVocabularyOutputPrompt,
  generateVocabularyTest,
  getContextReplayRetryQueue,
  getDueVocabulary,
  getVocabularyBankSummary,
  getVocabularyList,
  getVocabularyScenarios,
  getVocabularyStrategyInsights,
  getVocabularyStats,
  importVocabularyScenario,
  getPrioritizedWrongReviewQueue,
  normalizeUiError,
  reviewVocabularyWord,
  startTodayVocabularySession,
  startVocabularySession,
  submitVocabularyLearningAttempt,
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
const sourceOptions = ['manual', 'ielts_bank', 'scenario_pack', 'auto_collect', 'reading', 'listening', 'writing', 'speaking'];
const metaIgnoreTags = new Set(['scenario', 'manual']);
const sourceLabelMap = {
  manual: '手动添加',
  ielts_bank: '智能推荐',
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
const levelLabelMap = {
  basic: '基础',
  intermediate: '进阶',
  advanced: '高阶',
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
const levelLabel = (value) => levelLabelMap[value] || value || '适中';
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
    `场景:${moduleLabel(module)}`,
    ...uniqTopics.map((x) => `主题:${topicLabel(x)}`),
  ];
  return { source, module, topics: uniqTopics, chips };
};

const learnButtons = [
  { label: '不认识', delta: -0.2, rating: 'unknown' },
  { label: '模糊', delta: 0.05, rating: 'fuzzy' },
  { label: '认识', delta: 0.2, rating: 'known' },
];

const reviewButtons = [
  { label: '再复习', delta: -0.2 },
  { label: '较难', delta: -0.05 },
  { label: '掌握', delta: 0.12 },
  { label: '熟练', delta: 0.22 },
];

const todaySteps = [
  { key: 'recall', label: '主动回忆' },
  { key: 'cloze', label: '例句填空' },
  { key: 'output', label: '造句输出' },
];

const learningModeOptions = [
  { value: 'auto', label: '智能推荐' },
  { value: 'cognitive', label: '认知模式' },
  { value: 'consolidation', label: '巩固模式' },
  { value: 'output', label: '输出模式' },
];

const learningModeLabelMap = Object.fromEntries(learningModeOptions.map((item) => [item.value, item.label]));

const learningModeSteps = {
  cognitive: [
    { key: 'recall', label: '主动回忆' },
  ],
  consolidation: [
    { key: 'cloze', label: '例句填空' },
    { key: 'collocation', label: '搭配回忆' },
  ],
  output: [
    { key: 'translation', label: '短句转换' },
    { key: 'output', label: '造句输出' },
  ],
};

const initialStepForMode = (mode) => {
  const steps = learningModeSteps[mode] || todaySteps;
  return steps[0]?.key || 'recall';
};

const todaySessionStorageKey = 'vocab_today_learning_session_v1';

const localDateKey = () => {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const resolveAutoLearningMode = (wordRow) => {
  const mastery = Number(wordRow?.mastery_level || 0);
  const examples = Array.isArray(wordRow?.examples) ? wordRow.examples : [];
  if (mastery < 0.28) return 'cognitive';
  if (mastery < 0.68 || examples.length > 0) return 'consolidation';
  return 'output';
};

const getPrimaryExample = (wordRow) => {
  const first = (wordRow?.examples || [])[0];
  return String(first || '').trim();
};

const maskWordInExample = (sentence, word) => {
  const text = String(sentence || '').trim();
  const target = String(word || '').trim();
  if (!text || !target) return '';
  const escaped = target.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`\\b${escaped}\\b`, 'i');
  if (pattern.test(text)) return text.replace(pattern, '____');
  return `${text}  (${target})`;
};

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
  const [todayCount, setTodayCount] = useState(10);
  const [todayTopic, setTodayTopic] = useState('');
  const [todayDifficulty, setTodayDifficulty] = useState('');
  const [todayLearningMode, setTodayLearningMode] = useState('auto');
  const [todayStep, setTodayStep] = useState('recall');
  const [todayRecallAnswer, setTodayRecallAnswer] = useState('');
  const [todayClozeAnswer, setTodayClozeAnswer] = useState('');
  const [todayPracticeAnswer, setTodayPracticeAnswer] = useState('');
  const [todayOutputAnswer, setTodayOutputAnswer] = useState('');
  const [todayOutputHintVisible, setTodayOutputHintVisible] = useState(false);
  const [todayOutputPrompt, setTodayOutputPrompt] = useState('');
  const [todayOutputPromptLoading, setTodayOutputPromptLoading] = useState(false);
  const [todayAttemptFeedback, setTodayAttemptFeedback] = useState('');
  const [todayAttemptResult, setTodayAttemptResult] = useState(null);

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
  const [bankSummary, setBankSummary] = useState({ total: 0, difficulties: [], topics: [] });

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
  const testInputRefs = useRef({});
  const testOptionRefs = useRef({});
  const testSubmitBtnRef = useRef(null);
  const successTimerRef = useRef(null);
  const todayAutoStartTimerRef = useRef(null);
  const todayAutoAdvanceTimerRef = useRef(null);
  const todayAutoStartedRef = useRef(false);
  const todaySessionHydratedRef = useRef(false);
  const todaySessionRestoredRef = useRef(false);

  const wordById = useMemo(() => {
    const m = new Map();
    (words || []).forEach((w) => m.set(String(w.id), w));
    return m;
  }, [words]);

  const currentLearnWord = learnSession[learnIndex] || null;
  const currentReviewWord = reviewQueue[0] || null;
  const currentLearnExample = getPrimaryExample(currentLearnWord);
  const currentLearnCloze = maskWordInExample(currentLearnExample, currentLearnWord?.word);
  const activeLearningMode = todayLearningMode === 'auto'
    ? resolveAutoLearningMode(currentLearnWord)
    : todayLearningMode;
  const activeTodaySteps = learningModeSteps[activeLearningMode] || todaySteps;
  const wrongWords = useMemo(
    () => wrongWordIds.map((id) => wordById.get(String(id))).filter(Boolean),
    [wrongWordIds, wordById],
  );
  const strategySummary = useMemo(() => {
    const rows = Array.isArray(strategyInsights) ? strategyInsights : [];
    return {
      sessions: rows.reduce((sum, item) => sum + Number(item.session_count || 0), 0),
      words: rows.reduce((sum, item) => sum + Number(item.total_words || 0), 0),
    };
  }, [strategyInsights]);

  const clearSuccess = () => {
    if (successTimerRef.current) {
      window.clearTimeout(successTimerRef.current);
      successTimerRef.current = null;
    }
    setSuccessMessage('');
  };

  const clearTodayAutoAdvance = () => {
    if (todayAutoAdvanceTimerRef.current) {
      window.clearTimeout(todayAutoAdvanceTimerRef.current);
      todayAutoAdvanceTimerRef.current = null;
    }
  };

  const clearStoredTodaySession = () => {
    try {
      localStorage.removeItem(todaySessionStorageKey);
    } catch {
      // Ignore storage errors so learning flow stays usable.
    }
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

  const loadBankSummary = async () => {
    try {
      const data = await getVocabularyBankSummary();
      setBankSummary(data || { total: 0, difficulties: [], topics: [] });
    } catch {
      setBankSummary({ total: 0, difficulties: [], topics: [] });
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
    loadBankSummary();
  }, []);

  useEffect(() => {
    loadContextRetryQueue();
  }, [words]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(todaySessionStorageKey);
      if (!raw) {
        todaySessionHydratedRef.current = true;
        return;
      }
      const saved = JSON.parse(raw);
      const savedSession = Array.isArray(saved?.learnSession) ? saved.learnSession : [];
      const savedIndex = Number(saved?.learnIndex || 0);
      const isValid = saved?.dateKey === localDateKey()
        && savedSession.length > 0
        && savedIndex >= 0
        && savedIndex < savedSession.length;
      if (!isValid) {
        localStorage.removeItem(todaySessionStorageKey);
        todaySessionHydratedRef.current = true;
        return;
      }
      todaySessionRestoredRef.current = true;
      todayAutoStartedRef.current = true;
      setLearning(true);
      setLearnSession(savedSession);
      setLearnIndex(savedIndex);
      setLearnStrategy(saved.learnStrategy || 'today_active_recall');
      setTodayCount(saved.todayCount || 10);
      setTodayTopic(saved.todayTopic || '');
      setTodayDifficulty(saved.todayDifficulty || '');
      setTodayLearningMode(saved.todayLearningMode || 'auto');
      const restoredMode = (saved.todayLearningMode || 'auto') === 'auto'
        ? resolveAutoLearningMode(savedSession[savedIndex])
        : saved.todayLearningMode;
      const restoredSteps = learningModeSteps[restoredMode] || todaySteps;
      const restoredStepKeys = restoredSteps.map((step) => step.key);
      setTodayStep(restoredStepKeys.includes(saved.todayStep) ? saved.todayStep : initialStepForMode(restoredMode));
      setTodayRecallAnswer(saved.todayRecallAnswer || '');
      setTodayClozeAnswer(saved.todayClozeAnswer || '');
      setTodayPracticeAnswer(saved.todayPracticeAnswer || '');
      setTodayOutputAnswer(saved.todayOutputAnswer || '');
      setTodayOutputHintVisible(Boolean(saved.todayOutputHintVisible));
      setTodayOutputPrompt(saved.todayOutputPrompt || '');
      setTodayAttemptResult(saved.todayAttemptResult || null);
      setTodayAttemptFeedback(saved.todayAttemptFeedback || '');
      todaySessionHydratedRef.current = true;
    } catch {
      clearStoredTodaySession();
      todaySessionHydratedRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (!todaySessionHydratedRef.current) return;
    if (!learning || learnSession.length === 0) {
      clearStoredTodaySession();
      return;
    }
    const payload = {
      dateKey: localDateKey(),
      savedAt: Date.now(),
      learnSession,
      learnIndex,
      learnStrategy,
      todayCount,
      todayTopic,
      todayDifficulty,
      todayLearningMode,
      todayStep,
      todayRecallAnswer,
      todayClozeAnswer,
      todayPracticeAnswer,
      todayOutputAnswer,
      todayOutputHintVisible,
      todayOutputPrompt,
      todayAttemptResult,
      todayAttemptFeedback,
    };
    try {
      localStorage.setItem(todaySessionStorageKey, JSON.stringify(payload));
    } catch {
      // Ignore quota/private-mode errors; the current in-memory session still works.
    }
  }, [
    learning,
    learnSession,
    learnIndex,
    learnStrategy,
    todayCount,
    todayTopic,
    todayDifficulty,
    todayLearningMode,
    todayStep,
    todayRecallAnswer,
    todayClozeAnswer,
    todayPracticeAnswer,
    todayOutputAnswer,
    todayOutputHintVisible,
    todayOutputPrompt,
    todayAttemptResult,
    todayAttemptFeedback,
  ]);

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
      if (todayAutoStartTimerRef.current) {
        window.clearTimeout(todayAutoStartTimerRef.current);
      }
      clearTodayAutoAdvance();
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

  const focusNextTestInput = (currentQuestionId) => {
    const questions = testData?.questions || [];
    const idx = questions.findIndex((q) => q.id === currentQuestionId);
    if (idx < 0) return;
    for (let i = idx + 1; i < questions.length; i += 1) {
      const q = questions[i];
      const el = Array.isArray(q.options) && q.options.length > 0
        ? testOptionRefs.current[q.id]
        : testInputRefs.current[q.id];
      if (el) {
        el.focus();
        if (!Array.isArray(q.options) || q.options.length === 0) {
          el.select?.();
        }
        return;
      }
    }
    testSubmitBtnRef.current?.focus();
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
      setTodayStep('recall');
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

  const resetTodayInputs = () => {
    clearTodayAutoAdvance();
    setTodayRecallAnswer('');
    setTodayClozeAnswer('');
    setTodayPracticeAnswer('');
    setTodayOutputAnswer('');
    setTodayOutputHintVisible(false);
    setTodayOutputPrompt('');
    setTodayOutputPromptLoading(false);
    setTodayAttemptFeedback('');
    setTodayAttemptResult(null);
  };

  const onStartTodaySession = async ({ silent = false } = {}) => {
    try {
      setError('');
      if (!silent) clearSuccess();
      setLearning(true);
      setLearnIndex(0);
      resetTodayInputs();
      const session = await startTodayVocabularySession({
        count: Number(todayCount) || 10,
        topic: todayTopic || '',
        difficulty: todayDifficulty || '',
      });
      setLearnStrategy(session?.strategy || 'today_active_recall');
      const sessionWords = session.words || [];
      setLearnSession(sessionWords);
      const firstWord = sessionWords[0] || null;
      const firstMode = todayLearningMode === 'auto' ? resolveAutoLearningMode(firstWord) : todayLearningMode;
      setTodayStep(initialStepForMode(firstMode));
      const insightRows = await getVocabularyStrategyInsights(14);
      setStrategyInsights(insightRows || []);
      if (!session?.words?.length) {
        setLearning(false);
        if (!silent) showSuccess('暂无可学习词汇，请调整话题、难度或稍后再试。');
      }
    } catch (err) {
      setError(typeof err === 'string' ? err : '开启今日学习失败');
      setLearning(false);
    }
  };

  const onLearnRate = async (delta, rating = 'fuzzy') => {
    if (!currentLearnWord) return;
    try {
      const isTodaySession = learnStrategy === 'today_active_recall';
      let result = null;
      if (isTodaySession) {
        result = await submitVocabularyLearningAttempt({
          vocab_id: currentLearnWord.id,
          session_id: '',
          strategy: learnStrategy,
          recall_text: todayRecallAnswer,
          cloze_answer: todayClozeAnswer,
          output_sentence: [todayPracticeAnswer, todayOutputAnswer].filter(Boolean).join('\n'),
          self_rating: rating,
        });
      } else {
        result = await reviewVocabularyWord(currentLearnWord.id, delta);
      }
      setTodayReviewed((x) => x + 1);
      if (isTodaySession && result?.feedback) {
        setTodayAttemptFeedback(result.feedback);
        setTodayAttemptResult(result);
        return;
      }
      await advanceLearningWord(false);
    } catch (err) {
      setError(typeof err === 'string' ? err : '学习反馈保存失败');
    }
  };

  const onToggleOutputHint = async () => {
    const nextVisible = !todayOutputHintVisible;
    setTodayOutputHintVisible(nextVisible);
    if (!nextVisible || todayOutputPrompt || !currentLearnWord?.id) return;
    try {
      setTodayOutputPromptLoading(true);
      setError('');
      const result = await generateVocabularyOutputPrompt(currentLearnWord.id, todayTopic || '');
      setTodayOutputPrompt(result?.chinese_sentence || '');
    } catch (err) {
      setError(typeof err === 'string' ? err : '生成中文提示失败');
    } finally {
      setTodayOutputPromptLoading(false);
    }
  };

  const advanceLearningWord = async (showDoneMessage = true) => {
    if (!currentLearnWord) return;
    clearTodayAutoAdvance();
    try {
      if (learnIndex + 1 >= learnSession.length) {
        setLearning(false);
        setLearnSession([]);
        setLearnIndex(0);
        clearStoredTodaySession();
        if (showDoneMessage) showSuccess('学习会话完成');
        await loadWords();
        return;
      }
      setLearnIndex((x) => x + 1);
      resetTodayInputs();
      const nextWord = learnSession[learnIndex + 1];
      const nextMode = todayLearningMode === 'auto' ? resolveAutoLearningMode(nextWord) : todayLearningMode;
      setTodayStep(initialStepForMode(nextMode));
    } catch (err) {
      setError(typeof err === 'string' ? err : '切换下一词失败');
    }
  };

  useEffect(() => {
    if (!todaySessionHydratedRef.current || todaySessionRestoredRef.current) return;
    if (todayAutoStartedRef.current) return;
    todayAutoStartedRef.current = true;
    todayAutoStartTimerRef.current = window.setTimeout(() => {
      todayAutoStartTimerRef.current = null;
      onStartTodaySession({ silent: true });
    }, 80);
    return () => {
      if (todayAutoStartTimerRef.current) {
        window.clearTimeout(todayAutoStartTimerRef.current);
        todayAutoStartTimerRef.current = null;
      }
    };
  }, []);

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
      window.setTimeout(() => {
        const first = (data?.questions || [])[0];
        if (!first) return;
        const el = Array.isArray(first.options) && first.options.length > 0
          ? testOptionRefs.current[first.id]
          : testInputRefs.current[first.id];
        el?.focus();
      }, 60);
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
        <div className="card vocab-card vocab-overview-card">
          <h3>今日概览</h3>
          <MetricGrid className="vocab-overview-grid">
            <MetricCard label="词汇总数" value={stats.total || 0} />
            <MetricCard label="到期复习" value={stats.due_count || 0} />
            <MetricCard label="平均掌握度" value={`${Math.round((stats.avg_mastery || 0) * 100)}%`} />
            <MetricCard label="今日已练" value={todayReviewed} />
            <MetricCard label="错词待复习" value={wrongWords.length} />
          </MetricGrid>
        </div>

        <div className="card vocab-card vocab-card-primary-learning">
          <h3>今日学习</h3>
          <div className="vocab-learning-hero">
            <div>
              <strong>推荐路径：智能推荐</strong>
              <p>进入页面后会自动准备今日词；根据掌握情况选择认知、巩固或输出训练。</p>
            </div>
            <div className="vocab-learning-hero-steps">
              <span>选词</span>
              <span>回忆</span>
              <span>语境</span>
              <span>输出</span>
              <span>复习</span>
            </div>
          </div>
          <ToolbarRow className="vocab-actions-row">
            <select value={todayTopic} onChange={(e) => setTodayTopic(e.target.value)}>
              <option value="">全部话题</option>
              {(bankSummary.topics || []).slice(0, 16).map((item) => (
                <option key={item.topic} value={item.topic}>{topicLabel(item.topic)}</option>
              ))}
            </select>
            <select value={todayDifficulty} onChange={(e) => setTodayDifficulty(e.target.value)}>
              <option value="">智能难度</option>
              <option value="easy">基础</option>
              <option value="medium">进阶</option>
              <option value="hard">高阶</option>
            </select>
            <select value={todayLearningMode} onChange={(e) => setTodayLearningMode(e.target.value)}>
              {learningModeOptions.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            <input
              type="number"
              min="3"
              max="20"
              value={todayCount}
              onChange={(e) => setTodayCount(e.target.value)}
              style={{ width: 90 }}
            />
            <button className="vocab-btn vocab-btn-primary" onClick={onStartTodaySession}>
              重新安排今日学习
            </button>
            <button className="vocab-btn vocab-btn-secondary" onClick={() => onStartSession('mixed')}>
              快速复习
            </button>
          </ToolbarRow>
          {strategyInsights.length > 0 && (
            <p style={{ marginTop: 8, fontSize: 13, color: '#4a5568' }}>
              近14天已完成 {strategySummary.sessions} 次词汇学习，共练习 {strategySummary.words} 个词。
            </p>
          )}
          {learning && currentLearnWord && (
            <div className="vocab-focus-panel">
              <p>
                进度：{learnIndex + 1}/{learnSession.length}
                {' · '}
                学习形式：{todayLearningMode === 'auto' ? `智能推荐：${learningModeLabelMap[activeLearningMode]}` : learningModeLabelMap[activeLearningMode]}
              </p>
              <div className="vocab-chip-wrap" style={{ margin: '8px 0 12px' }}>
                {activeTodaySteps.map((step) => (
                  <button
                    key={step.key}
                    className={`vocab-step-chip${todayStep === step.key ? ' active' : ''}`}
                    onClick={() => setTodayStep(step.key)}
                    type="button"
                  >
                    {step.label}
                  </button>
                ))}
              </div>
              {todayStep === 'recall' && (
                <div>
                  <h4 style={{ marginBottom: 6 }}>{currentLearnWord.word}</h4>
                  <p style={{ color: '#64748b' }}>先不要看答案，写下你能想到的释义、搭配或使用场景。</p>
                  <textarea
                    rows={4}
                    value={todayRecallAnswer}
                    onChange={(e) => setTodayRecallAnswer(e.target.value)}
                    placeholder="例如：意思、常见搭配、在哪类雅思话题中使用..."
                    style={{ width: '100%' }}
                  />
                </div>
              )}
              {todayStep === 'cloze' && (
                <div>
                  <h4 style={{ marginBottom: 6 }}>例句填空</h4>
                  <p>{currentLearnCloze || `根据释义写出目标词：${currentLearnWord.definition || currentLearnWord.word}`}</p>
                  <input
                    value={todayClozeAnswer}
                    onChange={(e) => setTodayClozeAnswer(e.target.value)}
                    placeholder="输入目标词"
                    style={{ width: '100%', marginBottom: 8 }}
                  />
                  {todayClozeAnswer.trim() && (
                    <p style={{ color: todayClozeAnswer.trim().toLowerCase() === String(currentLearnWord.word || '').toLowerCase() ? '#047857' : '#b45309' }}>
                      {todayClozeAnswer.trim().toLowerCase() === String(currentLearnWord.word || '').toLowerCase()
                        ? '填得对，继续把它用出来。'
                        : `目标词是：${currentLearnWord.word}`}
                    </p>
                  )}
                  <button className="vocab-btn vocab-btn-primary" type="button" onClick={() => setTodayStep('output')}>
                    进入造句
                  </button>
                </div>
              )}
              {todayStep === 'collocation' && (
                <div>
                  <h4 style={{ marginBottom: 6 }}>搭配回忆</h4>
                  <p style={{ color: '#64748b' }}>写出一个你认为和目标词自然搭配的短语，或者用它补全一个表达。</p>
                  <input
                    value={todayPracticeAnswer}
                    onChange={(e) => setTodayPracticeAnswer(e.target.value)}
                    placeholder={`例如：常见动词 + ${currentLearnWord.word} / ${currentLearnWord.word} + 常见名词`}
                    style={{ width: '100%', marginBottom: 8 }}
                  />
                  {todayPracticeAnswer.trim() && !todayPracticeAnswer.toLowerCase().includes(String(currentLearnWord.word || '').toLowerCase()) && (
                    <p style={{ color: '#b45309' }}>建议把目标词放进搭配里。</p>
                  )}
                </div>
              )}
              {todayStep === 'translation' && (
                <div>
                  <h4 style={{ marginBottom: 6 }}>短句转换</h4>
                  <p style={{ color: '#64748b' }}>
                    用目标词表达这个意思：{currentLearnWord.definition || `使用 ${currentLearnWord.word} 写一个短句`}
                  </p>
                  <textarea
                    rows={4}
                    value={todayPracticeAnswer}
                    onChange={(e) => setTodayPracticeAnswer(e.target.value)}
                    placeholder={`用 ${currentLearnWord.word} 写一个自然的英文短句`}
                    style={{ width: '100%' }}
                  />
                  {todayPracticeAnswer.trim() && !todayPracticeAnswer.toLowerCase().includes(String(currentLearnWord.word || '').toLowerCase()) && (
                    <p style={{ color: '#b45309' }}>建议在短句中使用目标词。</p>
                  )}
                </div>
              )}
              {todayStep === 'output' && (
                <div>
                  <h4 style={{ marginBottom: 6 }}>造句输出</h4>
                  <p style={{ color: '#64748b' }}>目标词：{currentLearnWord.word}</p>
                  <button
                    className="vocab-btn vocab-btn-secondary"
                    type="button"
                    onClick={onToggleOutputHint}
                    disabled={todayOutputPromptLoading}
                    style={{ marginBottom: 8 }}
                  >
                    {todayOutputHintVisible ? '隐藏提示' : (todayOutputPromptLoading ? '生成中...' : '查看提示')}
                  </button>
                  {todayOutputHintVisible && (
                    <div className="vocab-subpanel" style={{ marginBottom: 10 }}>
                      <p style={{ margin: 0 }}>
                        {todayOutputPromptLoading ? '正在生成中文句子...' : `请翻译：${todayOutputPrompt || '请稍候...'}`}
                      </p>
                    </div>
                  )}
                  <textarea
                    rows={4}
                    value={todayOutputAnswer}
                    onChange={(e) => setTodayOutputAnswer(e.target.value)}
                    placeholder={`用 ${currentLearnWord.word} 写一个自然的英文句子`}
                    style={{ width: '100%' }}
                  />
                  {todayOutputAnswer.trim() && !todayOutputAnswer.toLowerCase().includes(String(currentLearnWord.word || '').toLowerCase()) && (
                    <p style={{ color: '#b45309' }}>建议把目标词自然放进句子里。</p>
                  )}
                </div>
              )}
              <div className="vocab-actions-row">
                {learnButtons.map((b) => (
                  <button
                    className="vocab-btn vocab-btn-secondary"
                    key={b.label}
                    disabled={Boolean(todayAttemptResult)}
                    onClick={() => onLearnRate(b.delta, b.rating)}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
              {todayAttemptResult && (
                <div className="vocab-learning-result">
                  <div>
                    <strong>{currentLearnWord.word}</strong>
                    <p>释义：{currentLearnWord.definition || '暂无释义'}</p>
                    {currentLearnWord.part_of_speech && <p>词性：{currentLearnWord.part_of_speech}</p>}
                    {currentLearnWord.pronunciation && <p>发音：/{currentLearnWord.pronunciation}/</p>}
                    {currentLearnExample && <p>例句：{currentLearnExample}</p>}
                    {(todayAttemptResult.output_feedback || todayAttemptResult.output_suggestion) && (
                      <div>
                        {todayAttemptResult.output_feedback && <p>句子反馈：{todayAttemptResult.output_feedback}</p>}
                        {todayAttemptResult.output_suggestion && <p>参考表达：{todayAttemptResult.output_suggestion}</p>}
                      </div>
                    )}
                  </div>
                  <button className="vocab-btn vocab-btn-primary" type="button" onClick={() => advanceLearningWord(true)}>
                    {learnIndex + 1 >= learnSession.length ? '完成学习' : '进入下一题'}
                  </button>
                </div>
              )}
            </div>
          )}
          {!learning && <p>正在准备今日学习；也可以调整话题、难度和数量后重新安排。</p>}
        </div>

        <div className="card vocab-card">
          <h3>复习巩固</h3>
          <div className="vocab-actions-row">
            <button className="vocab-btn vocab-btn-primary" onClick={() => startReview('due')}>开始到期复习</button>
            <button className="vocab-btn vocab-btn-primary" onClick={() => startReview('wrong')} disabled={wrongWords.length === 0}>仅练错词</button>
          </div>
          {reviewing && currentReviewWord && (
            <div className="vocab-focus-panel">
              <p>模式：{reviewMode === 'wrong' ? '错词专项' : '到期复习'}</p>
              {reviewMode === 'wrong' && (
                <p>
                  记忆风险：{Math.round(Number(currentReviewWord.priority_score || 0) * 100)}%
                  {' · '}
                  {currentReviewWord.priority_reason || '需要优先复习'}
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
                    <th align="left">记忆风险</th>
                    <th align="left">依据</th>
                  </tr>
                </thead>
                <tbody>
                  {wrongPriorityQueue.slice(0, 8).map((w) => (
                    <tr key={w.id}>
                      <td>{w.word}</td>
                      <td>{Math.round(Number(w.priority_score || 0) * 100)}%</td>
                      <td>{w.priority_reason || '需要优先复习'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
              {wrongPriorityQueue.length > 8 && (
                <p style={{ marginTop: 6, opacity: 0.8 }}>
                  仅展示前 8 个需要优先复习的词（共 {wrongPriorityQueue.length} 个）。
                </p>
              )}
            </div>
          )}
        </div>

        <div className="card vocab-card">
          <h3>专项词汇</h3>
          <div className="vocab-actions-row">
            <select value={scenarioModule} onChange={(e) => setScenarioModule(e.target.value)}>
              <option value="">全部模块</option>
              <option value="listening">听力</option>
              <option value="reading">阅读</option>
              <option value="writing">写作</option>
              <option value="speaking">口语</option>
            </select>
            <input
              placeholder="话题，如 environment"
              value={scenarioTopic}
              onChange={(e) => setScenarioTopic(e.target.value)}
              style={{ width: 220 }}
            />
            <button className="vocab-btn vocab-btn-secondary" onClick={loadScenarios}>刷新专项词</button>
          </div>
          <div className="vocab-test-list">
            {(scenarios || []).map((pack) => (
              <div key={`${pack.module}_${pack.topic}`} className="vocab-test-item">
                <p>
                  <strong>{moduleLabel(pack.module)} / {topicLabel(pack.topic)}</strong> · 难度：{levelLabel(pack.level)} ·
                  学习进度：{pack.learned_count}/{pack.total_count}
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
                      showSuccess(`已加入 ${result.imported} 词，已有 ${result.skipped_existing} 词`);
                      await Promise.all([loadWords(), loadScenarios()]);
                    } catch (err) {
                      setError(typeof err === 'string' ? err : '加入专项词汇失败');
                    }
                  }}
                >
                  加入学习
                </button>
              </div>
            ))}
            {scenarios.length === 0 && <p>暂无专项词汇</p>}
          </div>
        </div>

        <div className="card vocab-card">
          <h3>从材料收词</h3>
          <div className="vocab-actions-row">
            <select value={collectSource} onChange={(e) => setCollectSource(e.target.value)}>
              <option value="reading">阅读</option>
              <option value="listening">听力</option>
              <option value="writing">写作</option>
              <option value="speaking">口语</option>
            </select>
            <input
              placeholder="话题"
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
          <h3>语境复现训练</h3>
          <div className="vocab-actions-row">
            <select value={contextMode} onChange={(e) => setContextMode(e.target.value)}>
              <option value="cloze">填空训练</option>
              <option value="multiple_choice">选择训练</option>
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
                  {q.hint && <p style={{ opacity: 0.7 }}>提示：{q.hint}</p>}
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
                            onChange={() => {
                              setContextAnswers((prev) => ({ ...prev, [q.id]: opt }));
                              window.setTimeout(() => focusNextContextInput(q.id), 0);
                            }}
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
              <p>得分：{contextResult.correct}/{contextResult.total}（正确率：{Math.round((contextResult.accuracy || 0) * 100)}%）</p>
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
              <h4 style={{ marginBottom: 8 }}>错题强化练习</h4>
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
                      <th align="left">记忆风险</th>
                      <th align="left">原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contextRetryQueue.slice(0, 8).map((item) => (
                      <tr key={item.word_id}>
                        <td>{item.word}</td>
                        <td>{item.wrong_count}</td>
                        <td>{Math.round(Number(item.priority_score || 0) * 100)}%</td>
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
          <h3>词汇测试</h3>
          <div className="vocab-actions-row">
            <select value={testMode} onChange={(e) => setTestMode(e.target.value)}>
              <option value="multiple_choice">释义选择</option>
              <option value="spelling">拼写练习</option>
              <option value="fill_blank">例句填空</option>
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
            <button className="vocab-btn vocab-btn-primary" onClick={onSubmitTest} disabled={!testData?.test_id} ref={testSubmitBtnRef}>提交测试</button>
          </div>
          {testData && (
            <div className="vocab-test-list">
              {(testData.questions || []).map((q, idx) => (
                <div key={q.id} className="vocab-test-item">
                  <p style={{ marginBottom: 6 }}>{idx + 1}. {q.prompt}</p>
                  {Array.isArray(q.options) && q.options.length > 0 ? (
                    <div style={{ display: 'grid', gap: 4 }}>
                      {q.options.map((opt, optionIndex) => (
                        <label key={opt}>
                          <input
                            type="radio"
                            name={q.id}
                            ref={(el) => {
                              if (el && optionIndex === 0) testOptionRefs.current[q.id] = el;
                            }}
                            checked={testAnswers[q.id] === opt}
                            onChange={() => {
                              setTestAnswers((prev) => ({ ...prev, [q.id]: opt }));
                              window.setTimeout(() => focusNextTestInput(q.id), 0);
                            }}
                          />
                          {opt}
                        </label>
                      ))}
                    </div>
                  ) : (
                    <input
                      ref={(el) => {
                        if (el) testInputRefs.current[q.id] = el;
                      }}
                      value={testAnswers[q.id] || ''}
                      onChange={(e) => setTestAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      onKeyDown={(e) => {
                        if (e.key !== 'Enter') return;
                        e.preventDefault();
                        focusNextTestInput(q.id);
                      }}
                      placeholder="输入答案"
                    />
                  )}
                </div>
              ))}
            </div>
          )}
          {testResult && (
            <div style={{ marginTop: 10 }}>
              <p>得分：{testResult.correct}/{testResult.total}（正确率：{Math.round((testResult.accuracy || 0) * 100)}%）</p>
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
            <input placeholder="单词" value={wordForm.word} onChange={(e) => setWordForm({ ...wordForm, word: e.target.value })} required />
            <input placeholder="释义" value={wordForm.definition} onChange={(e) => setWordForm({ ...wordForm, definition: e.target.value })} />
            <input placeholder="例句，用 | 分隔" value={wordForm.examples} onChange={(e) => setWordForm({ ...wordForm, examples: e.target.value })} />
            <input placeholder="发音" value={wordForm.pronunciation} onChange={(e) => setWordForm({ ...wordForm, pronunciation: e.target.value })} />
            <input placeholder="词性" value={wordForm.part_of_speech} onChange={(e) => setWordForm({ ...wordForm, part_of_speech: e.target.value })} />
            <select value={wordForm.source_module} onChange={(e) => setWordForm({ ...wordForm, source_module: e.target.value })}>
              {sourceOptions.map((x) => <option key={x} value={x}>{sourceLabel(x)}</option>)}
            </select>
            <select value={wordForm.module_tag} onChange={(e) => setWordForm({ ...wordForm, module_tag: e.target.value })}>
              {moduleTagOptions.map((x) => <option key={x} value={x}>{moduleLabel(x)}</option>)}
            </select>
            <input
              placeholder="话题标签，逗号分隔，如 accommodation,education"
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
              placeholder="关键词搜索（单词/释义）"
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
