import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SidebarMenu from '../components/layout/SidebarMenu';
import {
  addVocabularyWord,
  autoCollectVocabulary,
  generateContextReplay,
  generateVocabularyOutputPrompt,
  generateVocabularyTest,
  getContextReplayRetryQueue,
  getDueVocabulary,
  getTodayVocabularyLearningStatus,
  getVocabularyBankSummary,
  getVocabularyList,
  getVocabularyScenarios,
  getVocabularyStrategyInsights,
  getVocabularyStats,
  getVocabularyWordAudio,
  importVocabularyScenario,
  getPrioritizedWrongReviewQueue,
  normalizeUiError,
  reviewVocabularyWord,
  setTodayVocabularyLearningStatus,
  startTodayVocabularySession,
  submitVocabularyLearningAttempt,
  submitContextReplay,
  submitVocabularyTest,
} from '../utils/api';
import { MetricCard, MetricGrid } from '../components/layout/DesktopUI';

import TopNav from "../components/layout/TopNav";
const API_BASE = String(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
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

const todayRatingChoices = [
  { label: '完全忘了', rating: 'forgot', quality: 1 },
  { label: '有点模糊', rating: 'hard', quality: 2 },
  { label: '想起来了', rating: 'recalled', quality: 3 },
  { label: '比较熟', rating: 'familiar', quality: 4 },
  { label: '很轻松', rating: 'easy', quality: 5 },
];

const reviewButtons = [
  { label: '完全忘了', delta: -0.2, quality: 1, hint: '稍后再巩固' },
  { label: '有点模糊', delta: -0.05, quality: 2, hint: '短间隔复习' },
  { label: '想起来了', delta: 0.08, quality: 3, hint: '明天左右' },
  { label: '比较熟', delta: 0.14, quality: 4, hint: '间隔拉长' },
  { label: '很轻松', delta: 0.22, quality: 5, hint: '长期巩固' },
];

const formatReviewTime = (ts) => {
  if (!ts) return '';
  const date = new Date(Number(ts) * 1000);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const nextPracticeStepForQuality = (quality) => {
  if (quality <= 2) return 'recognition';
  if (quality === 3) return 'cloze';
  return 'output';
};

const todaySessionStorageKey = 'vocab_today_learning_session_v1';

const localDateKey = () => {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const getPrimaryExample = (wordRow) => {
  const first = (wordRow?.examples || [])[0];
  return String(first || '').trim();
};

const getWordDefinition = (wordRow) => String(wordRow?.definition || '').trim() || '暂无释义';

const maskWordInExample = (sentence, word) => {
  const text = String(sentence || '').trim();
  const target = String(word || '').trim();
  if (!text || !target) return '';
  const escaped = target.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`\\b${escaped}\\b`, 'i');
  if (pattern.test(text)) return text.replace(pattern, '____');
  return `${text}  (${target})`;
};

const hashText = (value) => String(value || '').split('').reduce((sum, ch) => sum + ch.charCodeAt(0), 0);

const buildRecognitionOptions = (targetWord, allWords = []) => {
  const targetId = String(targetWord?.id ?? '');
  const wordText = String(targetWord?.word ?? '').trim();
  // 只要还有目标词（即使缺 id）就至少给出正确项，避免识别步骤无选项卡死。
  if (!targetId && !wordText) return [];
  const key = targetId || `word:${wordText.toLowerCase()}`;
  const seed = hashText(wordText || key);
  const correct = {
    key,
    value: wordText,
    label: getWordDefinition(targetWord) || wordText || '（正确项）',
    correct: true,
  };
  const distractors = (Array.isArray(allWords) ? allWords : [])
    .filter(
      (item) =>
        String(item?.id ?? '') !== targetId &&
        String(item?.word ?? '').trim().toLowerCase() !== wordText.toLowerCase() &&
        String(item?.definition ?? '').trim(),
    )
    // 用带种子的排序让干扰项随目标词变化，避免每次都取同样的前 12 个词。
    .sort((a, b) => (hashText(String(a?.id ?? '')) + seed) - (hashText(String(b?.id ?? '')) + seed))
    .slice(0, 3)
    .map((item) => ({
      key: String(item.id),
      value: String(item.word || ''),
      label: getWordDefinition(item),
      correct: false,
    }));
  return [correct, ...distractors].sort(
    (a, b) => ((hashText(a.key) + seed) % 97) - ((hashText(b.key) + seed) % 97),
  );
};

const definitionStopwords = new Set([
  'the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'used', 'use',
  'thing', 'person', 'people', 'something', 'someone', '暂无释义',
]);

const extractDefinitionKeywords = (definition) => {
  const raw = String(definition || '').trim();
  if (!raw) return [];
  const english = raw
    .toLowerCase()
    .match(/[a-z][a-z'-]{3,}/g) || [];
  const chinese = raw
    .split(/[，。；;,.、/（）()：:\s]+/)
    .map((x) => x.trim())
    .filter((x) => /[\u4e00-\u9fff]/.test(x) && x.length >= 2);
  const keywords = [...english, ...chinese]
    .map((x) => x.replace(/^to\s+/, '').trim())
    .filter((x) => x && !definitionStopwords.has(x));
  return Array.from(new Set(keywords)).slice(0, 8);
};

const evaluateRecallAgainstDefinition = (answer, definition) => {
  const text = String(answer || '').trim().toLowerCase();
  const keywords = extractDefinitionKeywords(definition);
  if (!text) {
    return {
      score: 0,
      matched: [],
      keywords,
      suggestedRating: 'forgot',
      message: '',
    };
  }
  if (keywords.length === 0) {
    return {
      score: 0.35,
      matched: [],
      keywords,
      suggestedRating: 'hard',
      message: '',
    };
  }
  const matched = keywords.filter((keyword) => text.includes(keyword.toLowerCase()));
  const score = matched.length / keywords.length;
  if (score >= 0.72) {
    return {
      score,
      matched,
      keywords,
      suggestedRating: 'familiar',
      message: '',
    };
  }
  if (score >= 0.42) {
    return {
      score,
      matched,
      keywords,
      suggestedRating: 'recalled',
      message: '',
    };
  }
  if (score >= 0.18) {
    return {
      score,
      matched,
      keywords,
      suggestedRating: 'hard',
      message: '',
    };
  }
  return {
    score,
    matched,
    keywords,
    suggestedRating: 'forgot',
    message: '',
  };
};

const escapeRegExp = (value) => String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const cleanupIssueCorrection = (value) => String(value || '')
  .replace(/^[\s'"‘’“”]+|[\s'"‘’“”，。；;]+$/g, '')
  .trim();

const extractSentenceIssues = (feedback) => {
  const text = String(feedback || '');
  const issues = [];
  const patterns = [
    /['‘’"]([^'‘’"]{1,80})['‘’"]\s*(?:应为|应该为|应改为|改为|换成|→|->)\s*['‘’"]([^'‘’"]{1,120})['‘’"]/g,
    /(?:把|将)\s*['‘’"]([^'‘’"]{1,80})['‘’"]\s*(?:改为|换成|改成)\s*['‘’"]([^'‘’"]{1,120})['‘’"]/g,
  ];
  patterns.forEach((pattern) => {
    let match = pattern.exec(text);
    while (match) {
      const phrase = String(match[1] || '').trim();
      const correction = cleanupIssueCorrection(match[2]);
      if (phrase && /[A-Za-z]/.test(phrase)) {
        issues.push({
          phrase,
          correction,
          reason: match[0],
        });
      }
      match = pattern.exec(text);
    }
  });
  return Array.from(new Set(issues.map((x) => x.phrase.toLowerCase())))
    .map((lower) => issues.find((x) => x.phrase.toLowerCase() === lower))
    .filter(Boolean)
    .slice(0, 5);
};

const formatSentenceIssueTooltip = (issue) => {
  const correction = String(issue?.correction || '').trim();
  const reason = String(issue?.reason || '').trim();
  if (correction) return `建议改为：${correction}\n原因：${reason}`;
  return reason || '这里需要调整';
};

const renderAnnotatedSentence = (sentence, feedback) => {
  const text = String(sentence || '').replace(/\s+/g, ' ').trim();
  const issues = extractSentenceIssues(feedback);
  if (!text || issues.length === 0) return text || '本轮没有提交造句。';
  const ranges = [];
  issues.forEach((issue, issueIndex) => {
    const pattern = new RegExp(escapeRegExp(issue.phrase), 'i');
    const match = pattern.exec(text);
    if (!match) return;
    const start = match.index;
    const end = start + match[0].length;
    if (ranges.some((range) => start < range.end && end > range.start)) return;
    ranges.push({ start, end, issue, issueIndex, value: match[0] });
  });
  if (ranges.length === 0) return text;
  ranges.sort((a, b) => a.start - b.start);
  const parts = [];
  let cursor = 0;
  ranges.forEach((range) => {
    if (range.start > cursor) parts.push(text.slice(cursor, range.start));
    parts.push(
      <span
        className={`vocab-sentence-mark issue-${range.issueIndex % 4}`}
        data-tooltip={formatSentenceIssueTooltip(range.issue)}
        key={`${range.start}-${range.end}`}
        tabIndex={0}
      >
        {range.value}
      </span>
    );
    cursor = range.end;
  });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
};

let activeVocabularyAudio = null;

const toAudioSrc = (url) => {
  const raw = String(url || '').trim();
  if (!raw) return '';
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
  if (raw.startsWith('/')) return `${API_BASE}${raw}`;
  return `${API_BASE}/${raw}`;
};

const playWordAudio = async (word) => {
  const text = String(word || '').trim();
  if (!text || typeof window === 'undefined') return null;
  const result = await getVocabularyWordAudio(text);
  const audioUrl = toAudioSrc(result?.audio_url);
  if (!audioUrl) return null;
  if (activeVocabularyAudio) {
    activeVocabularyAudio.pause();
    activeVocabularyAudio = null;
  }
  const audio = new Audio(audioUrl);
  activeVocabularyAudio = audio;
  try {
    await audio.play();
  } catch (err) {
    // 播放失败时同步清空全局引用，避免残留一个无法播放的实例。
    if (activeVocabularyAudio === audio) {
      activeVocabularyAudio = null;
    }
    throw err;
  }
  return audio;
};

const PronunciationLine = ({ word, pronunciation, strong = true }) => {
  const [audioState, setAudioState] = useState('idle');
  const audioRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      const audio = audioRef.current;
      if (audio) {
        audio.onended = null;
        audio.onerror = null;
        audio.onpause = null;
        audio.pause();
      }
      if (activeVocabularyAudio === audio) {
        activeVocabularyAudio = null;
      }
    };
  }, []);

  if (!pronunciation) return null;

  const setSafeAudioState = (nextState) => {
    if (mountedRef.current) setAudioState(nextState);
  };

  const handlePlayAudio = async () => {
    if (audioState !== 'idle') return;
    setAudioState('loading');
    try {
      const audio = await playWordAudio(word);
      if (!audio) {
        setSafeAudioState('idle');
        return;
      }
      audioRef.current = audio;
      audio.onended = () => setSafeAudioState('idle');
      audio.onerror = () => setSafeAudioState('idle');
      audio.onpause = () => setSafeAudioState('idle');
      setSafeAudioState('playing');
    } catch {
      setSafeAudioState('idle');
    }
  };

  const isBusy = audioState !== 'idle';
  const audioLabel = audioState === 'loading'
    ? '正在准备发音'
    : audioState === 'playing'
      ? '正在播放发音'
      : `播放 ${word} 的英文发音`;

  return (
    <p className="vocab-pronunciation-line">
      {strong ? <strong>发音：</strong> : '发音：'}
      <span className="vocab-pronunciation-text">/{pronunciation}/</span>
      <button
        aria-label={audioLabel}
        aria-busy={audioState === 'loading'}
        className={`vocab-audio-btn ${audioState === 'loading' ? 'is-loading' : ''} ${audioState === 'playing' ? 'is-playing' : ''}`}
        disabled={isBusy}
        onClick={handlePlayAudio}
        title={audioLabel}
        type="button"
      >
        <svg aria-hidden="true" className="vocab-audio-icon" fill="none" height="14" viewBox="0 0 24 24" width="14">
          <path
            d="M11 5 6.5 8.5H3.75A1.75 1.75 0 0 0 2 10.25v3.5c0 .97.78 1.75 1.75 1.75H6.5L11 19V5Z"
            stroke="currentColor"
            strokeLinejoin="round"
            strokeWidth="2"
          />
          <path
            d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2"
          />
        </svg>
        <span aria-hidden="true" className="vocab-audio-wave">
          <span />
          <span />
          <span />
        </span>
      </button>
    </p>
  );
};

function Vocabulary() {

  const navigate = useNavigate();
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
  const [todayStep, setTodayStep] = useState('recall');
  const [todayRecallAnswer, setTodayRecallAnswer] = useState('');
  const [todayClozeAnswer, setTodayClozeAnswer] = useState('');
  const [todayPracticeAnswer, setTodayPracticeAnswer] = useState('');
  const [todayOutputAnswer, setTodayOutputAnswer] = useState('');
  const [todayRecognitionAnswer, setTodayRecognitionAnswer] = useState('');
  const [todaySelfRating, setTodaySelfRating] = useState('');
  const [todayRecallEvaluation, setTodayRecallEvaluation] = useState(null);
  const [todayOutputHintVisible, setTodayOutputHintVisible] = useState(false);
  const [todayOutputPrompt, setTodayOutputPrompt] = useState('');
  const [todayOutputPromptLoading, setTodayOutputPromptLoading] = useState(false);
  const [todayAttemptFeedback, setTodayAttemptFeedback] = useState('');
  const [todayAttemptResult, setTodayAttemptResult] = useState(null);
  const [todayLearningCompleted, setTodayLearningCompleted] = useState(false);
  const [todayCompletionLoaded, setTodayCompletionLoaded] = useState(false);

  const [reviewQueue, setReviewQueue] = useState([]);
  const [reviewing, setReviewing] = useState(false);
  const [reviewMode, setReviewMode] = useState('due'); // due | wrong
  const [reviewNotice, setReviewNotice] = useState('');
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
  const submittedOutputSentence = [todayPracticeAnswer, todayOutputAnswer]
    .map((x) => String(x || '').trim())
    .filter(Boolean)
    .join('\n');
  const currentRecognitionOptions = useMemo(
    () => buildRecognitionOptions(currentLearnWord, words),
    [currentLearnWord, words],
  );
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

  const clearTodayCompletion = async () => {
    setTodayLearningCompleted(false);
    try {
      await setTodayVocabularyLearningStatus({ dateKey: localDateKey(), completed: false });
    } catch {
      // Keep the local visible state usable if Redis/API is temporarily unavailable.
    }
  };

  const markTodayLearningCompleted = async () => {
    setTodayLearningCompleted(true);
    try {
      await setTodayVocabularyLearningStatus({ dateKey: localDateKey(), completed: true });
    } catch {
      // Keep the local visible state usable if Redis/API is temporarily unavailable.
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
    let cancelled = false;
    const loadTodayCompletion = async () => {
      try {
        const status = await getTodayVocabularyLearningStatus(localDateKey());
        if (!cancelled) {
          setTodayLearningCompleted(Boolean(status?.completed));
        }
      } catch {
        if (!cancelled) {
          setTodayLearningCompleted(false);
        }
      } finally {
        if (!cancelled) {
          setTodayCompletionLoaded(true);
        }
      }
    };
    loadTodayCompletion();
    return () => {
      cancelled = true;
    };
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
      const restoredStepKeys = ['recall', 'reveal', 'recognition', 'cloze', 'output', 'result'];
      setTodayStep(restoredStepKeys.includes(saved.todayStep) ? saved.todayStep : 'recall');
      setTodayRecallAnswer(saved.todayRecallAnswer || '');
      setTodayClozeAnswer(saved.todayClozeAnswer || '');
      setTodayPracticeAnswer(saved.todayPracticeAnswer || '');
      setTodayOutputAnswer(saved.todayOutputAnswer || '');
      setTodayRecognitionAnswer(saved.todayRecognitionAnswer || '');
      setTodaySelfRating(saved.todaySelfRating || '');
      setTodayRecallEvaluation(saved.todayRecallEvaluation || null);
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
      todayStep,
      todayRecallAnswer,
      todayClozeAnswer,
      todayPracticeAnswer,
      todayOutputAnswer,
      todayRecognitionAnswer,
      todaySelfRating,
      todayRecallEvaluation,
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
    todayStep,
    todayRecallAnswer,
    todayClozeAnswer,
    todayPracticeAnswer,
    todayOutputAnswer,
    todayRecognitionAnswer,
    todaySelfRating,
    todayRecallEvaluation,
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

  const resetTodayInputs = () => {
    clearTodayAutoAdvance();
    setTodayRecallAnswer('');
    setTodayClozeAnswer('');
    setTodayPracticeAnswer('');
    setTodayOutputAnswer('');
    setTodayRecognitionAnswer('');
    setTodaySelfRating('');
    setTodayRecallEvaluation(null);
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
      await clearTodayCompletion();
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
      setTodayStep('recall');
      const insightRows = await getVocabularyStrategyInsights(14);
      setStrategyInsights(insightRows || []);
      if (!session?.words?.length) {
        setLearning(false);
        if (!silent) showSuccess('暂时没有可学习词汇，请稍后再试。');
      }
    } catch (err) {
      setError(typeof err === 'string' ? err : '开启今日学习失败');
      setLearning(false);
    }
  };

  const onChooseTodayRating = (choice) => {
    setTodaySelfRating(choice.rating);
    setTodayStep(nextPracticeStepForQuality(choice.quality));
  };

  const submitRecallAndReveal = (fallbackRating = '') => {
    if (!currentLearnWord) return;
    const evaluation = evaluateRecallAgainstDefinition(todayRecallAnswer, currentLearnWord.definition);
    const rating = fallbackRating || evaluation.suggestedRating || 'hard';
    setTodayRecallEvaluation(evaluation);
    setTodaySelfRating(rating);
    setTodayStep('reveal');
  };

  const roundSubmittingRef = useRef(false);
  const submitTodayLearningRound = async (overrides = {}) => {
    if (!currentLearnWord || roundSubmittingRef.current) return;
    roundSubmittingRef.current = true;
    clearTodayAutoAdvance();
    try {
      const isTodaySession = learnStrategy === 'today_active_recall';
      let result = null;
      if (isTodaySession) {
        const recognitionAnswer = overrides.recognitionAnswer ?? todayRecognitionAnswer;
        const recognitionOption = currentRecognitionOptions.find((item) => item.value === recognitionAnswer);
        result = await submitVocabularyLearningAttempt({
          vocab_id: currentLearnWord.id,
          session_id: '',
          strategy: learnStrategy,
          recall_text: todayRecallAnswer,
          cloze_answer: todayStep === 'recognition'
            ? (recognitionOption?.correct ? currentLearnWord.word : recognitionAnswer)
            : todayClozeAnswer,
          output_sentence: [todayPracticeAnswer, todayOutputAnswer].filter(Boolean).join('\n'),
          self_rating: todaySelfRating || 'fuzzy',
        });
      } else {
        result = await reviewVocabularyWord(currentLearnWord.id, 0.1);
      }
      setTodayReviewed((x) => x + 1);
      if (isTodaySession && result?.feedback) {
        setTodayAttemptFeedback(result.feedback);
        setTodayAttemptResult(result);
        setTodayStep('result');
        return;
      }
      await advanceLearningWord(false);
    } catch (err) {
      setError(typeof err === 'string' ? err : '学习反馈保存失败');
    } finally {
      roundSubmittingRef.current = false;
    }
  };

  const onChooseRecognition = (option) => {
    setTodayRecognitionAnswer(option.value);
    clearTodayAutoAdvance();
    todayAutoAdvanceTimerRef.current = window.setTimeout(() => {
      todayAutoAdvanceTimerRef.current = null;
      submitTodayLearningRound({ recognitionAnswer: option.value });
    }, 500);
  };

  const onSkipRecognition = () => {
    clearTodayAutoAdvance();
    advanceLearningWord(false);
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
        await markTodayLearningCompleted();
        if (showDoneMessage) showSuccess('已完成今日学习计划');
        await loadWords();
        return;
      }
      setLearnIndex((x) => x + 1);
      resetTodayInputs();
      setTodayStep('recall');
    } catch (err) {
      setError(typeof err === 'string' ? err : '切换下一词失败');
    }
  };

  useEffect(() => {
    if (!todaySessionHydratedRef.current || todaySessionRestoredRef.current) return;
    if (!todayCompletionLoaded) return;
    if (todayLearningCompleted) return;
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
  }, [todayCompletionLoaded, todayLearningCompleted]);

  const startReview = async (mode = 'due') => {
    setReviewMode(mode);
    setReviewNotice('');
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

  const reviewSubmittingRef = useRef(false);
  const onReviewRate = async (choice) => {
    if (!currentReviewWord || reviewSubmittingRef.current) return;
    reviewSubmittingRef.current = true;
    try {
      const result = await reviewVocabularyWord(currentReviewWord.id, choice.delta, choice.quality);
      const nextTime = formatReviewTime(result?.next_review_date);
      setReviewNotice(
        `${currentReviewWord.word} 已记录为「${choice.label}」${nextTime ? `，下次约 ${nextTime}` : ''}`
      );
      setTodayReviewed((x) => x + 1);
      const next = reviewQueue.slice(1);
      setReviewQueue(next);
      if (next.length === 0) {
        setReviewing(false);
      }
      await loadWords();
    } catch (err) {
      setError(typeof err === 'string' ? err : '复习记录失败');
    } finally {
      reviewSubmittingRef.current = false;
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
            <button className="vocab-btn vocab-btn-primary" onClick={() => navigate('/vocabulary/study?mode=auto&count=10')}>词库学习</button>
            <button className="vocab-btn vocab-btn-secondary" onClick={() => navigate('/vocabulary/book')}>词汇本管理</button>
            <button className="vocab-btn vocab-btn-secondary" onClick={loadWords}>刷新词汇</button>
          </div>
        </div>
        <div className="card vocab-card vocab-overview-card">
          <h3>今日概览</h3>
          <MetricGrid className="vocab-overview-grid">
            <MetricCard label="词汇总数" value={stats.total || 0} />
            <MetricCard label="到期复习" value={stats.due_count || 0} />
            <MetricCard label="今日已练" value={todayReviewed} />
            <MetricCard label="错词待复习" value={wrongWords.length} />
          </MetricGrid>
        </div>

        <div className="card vocab-card vocab-card-primary-learning">
          <h3>今日学习</h3>
          {strategyInsights.length > 0 && (
            <p style={{ marginTop: 8, fontSize: 13, color: '#4a5568' }}>
              近14天已完成 {strategySummary.sessions} 次词汇学习，共练习 {strategySummary.words} 个词。
            </p>
          )}
          {learning && currentLearnWord && (
            <div className="vocab-focus-panel">
              <div className="vocab-round-head">
                <span>第 {learnIndex + 1} / {learnSession.length} 个</span>
                {todaySelfRating && (
                  <strong>{todayRatingChoices.find((item) => item.rating === todaySelfRating)?.label}</strong>
                )}
              </div>
              {todayStep === 'recall' && (
                <div className="vocab-round-card">
                  <h4>{currentLearnWord.word}</h4>
                  <p>你记得它是什么意思吗？先主动回忆，再看答案。</p>
                  <textarea
                    rows={4}
                    value={todayRecallAnswer}
                    onChange={(e) => setTodayRecallAnswer(e.target.value)}
                    placeholder="写下你想到的释义、搭配或使用场景..."
                    style={{ width: '100%' }}
                  />
                  <div className="vocab-actions-row">
                    <button
                      className="vocab-btn vocab-btn-secondary"
                      type="button"
                      onClick={() => submitRecallAndReveal('forgot')}
                    >
                      想不起来
                    </button>
                    <button className="vocab-btn vocab-btn-primary" type="button" onClick={() => submitRecallAndReveal()}>
                      提交回忆并核对
                    </button>
                  </div>
                </div>
              )}
              {todayStep === 'reveal' && (
                <div className="vocab-round-card">
                  <h4>{currentLearnWord.word}</h4>
                  {todayRecallAnswer.trim() && (
                    <p><strong>你的回忆：</strong>{todayRecallAnswer.trim()}</p>
                  )}
                  <p><strong>释义：</strong>{getWordDefinition(currentLearnWord)}</p>
                  {currentLearnWord.part_of_speech && <p><strong>词性：</strong>{currentLearnWord.part_of_speech}</p>}
                  <PronunciationLine word={currentLearnWord.word} pronunciation={currentLearnWord.pronunciation} />
                  {currentLearnExample && <p><strong>例句：</strong>{currentLearnExample}</p>}
                  <div className="vocab-rating-grid">
                    {todayRatingChoices.map((choice) => (
                      <button
                        className={`vocab-btn vocab-btn-secondary${todaySelfRating === choice.rating ? ' active' : ''}`}
                        key={choice.rating}
                        type="button"
                        onClick={() => onChooseTodayRating(choice)}
                      >
                        {choice.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {todayStep === 'recognition' && (
                <div className="vocab-round-card">
                  <h4>选出最接近的意思</h4>
                  <p style={{ color: '#64748b' }}>目标词：{currentLearnWord.word}</p>
                  <div className="vocab-choice-grid">
                    {currentRecognitionOptions.map((option) => (
                      <button
                        className={`vocab-choice-option${todayRecognitionAnswer === option.value ? ' active' : ''}`}
                        key={option.key}
                        type="button"
                        onClick={() => onChooseRecognition(option)}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                  {currentRecognitionOptions.length === 0 && (
                    <p style={{ color: '#b45309' }}>暂无候选释义，可跳过本题。</p>
                  )}
                  {todayRecognitionAnswer && todayRecognitionAnswer !== String(currentLearnWord.word || '') && (
                    <p style={{ color: '#b45309' }}>
                      正确释义：{getWordDefinition(currentLearnWord)}
                    </p>
                  )}
                  <div className="vocab-actions-row" style={{ marginTop: 12 }}>
                    <button className="vocab-btn vocab-btn-secondary" type="button" onClick={onSkipRecognition}>
                      跳过这题
                    </button>
                  </div>
                </div>
              )}
              {todayStep === 'cloze' && (
                <div className="vocab-round-card">
                  <h4>例句填空</h4>
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
                        ? '填得对。'
                        : `目标词是：${currentLearnWord.word}`}
                    </p>
                  )}
                  <div className="vocab-actions-row">
                    <button className="vocab-btn vocab-btn-secondary" type="button" onClick={() => setTodayStep('output')}>
                      再造一句
                    </button>
                    <button className="vocab-btn vocab-btn-primary" type="button" onClick={() => submitTodayLearningRound()}>
                      提交填空并获取反馈
                    </button>
                  </div>
                </div>
              )}
              {todayStep === 'output' && (
                <div className="vocab-round-card">
                  <h4>造句输出</h4>
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
                  <div className="vocab-actions-row">
                    {!todayOutputAnswer.trim() && (
                      <button className="vocab-btn vocab-btn-secondary" type="button" onClick={() => submitTodayLearningRound()}>
                        跳过输出
                      </button>
                    )}
                    <button
                      className="vocab-btn vocab-btn-primary"
                      disabled={!todayOutputAnswer.trim()}
                      type="button"
                      onClick={() => submitTodayLearningRound()}
                    >
                      提交造句并获取反馈
                    </button>
                  </div>
                </div>
              )}
              {todayAttemptResult && (
                <div className="vocab-learning-result">
                  <div>
                    <strong>{currentLearnWord.word}</strong>
                    <p>释义：{currentLearnWord.definition || '暂无释义'}</p>
                    {currentLearnWord.part_of_speech && <p>词性：{currentLearnWord.part_of_speech}</p>}
                    <PronunciationLine word={currentLearnWord.word} pronunciation={currentLearnWord.pronunciation} strong={false} />
                    {currentLearnExample && <p>例句：{currentLearnExample}</p>}
                    {(submittedOutputSentence || todayAttemptResult.output_feedback || todayAttemptResult.output_suggestion) && (
                      <div className="vocab-output-review">
                        <div className="vocab-output-compare">
                          <div className="vocab-output-box reference">
                            <span>参考表达</span>
                            <p>{todayAttemptResult.output_suggestion || currentLearnExample || '暂无参考表达'}</p>
                          </div>
                          <div className="vocab-output-box user">
                            <span>你的句子</span>
                            <p>{renderAnnotatedSentence(submittedOutputSentence, todayAttemptResult.output_feedback)}</p>
                          </div>
                        </div>
                        <div className="vocab-output-feedback">
                          <span>点评</span>
                          <p>{todayAttemptResult.output_feedback || '这轮没有造句内容，建议下一次尝试用目标词写一个完整句子。'}</p>
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="vocab-learning-result-actions">
                    <button className="vocab-btn vocab-btn-primary" type="button" onClick={() => advanceLearningWord(true)}>
                      {learnIndex + 1 >= learnSession.length ? '完成学习' : '进入下一题'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          {!learning && <p>{todayLearningCompleted ? '已完成今日学习计划' : '正在准备今日学习。'}</p>}
        </div>

        <div className="card vocab-card">
          <h3>复习巩固</h3>
          <div className="vocab-actions-row">
            <button className="vocab-btn vocab-btn-primary" onClick={() => startReview('due')}>开始到期复习</button>
            <button className="vocab-btn vocab-btn-primary" onClick={() => startReview('wrong')} disabled={wrongWords.length === 0}>仅练错词</button>
          </div>
          {reviewing && currentReviewWord && (
            <div className="vocab-focus-panel">
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
                  <button className="vocab-btn vocab-btn-secondary vocab-review-choice" key={b.label} onClick={() => onReviewRate(b)}>
                    <span>{b.label}</span>
                    <small>{b.hint}</small>
                  </button>
                ))}
              </div>
            </div>
          )}
          {reviewNotice && <p className="vocab-review-notice">{reviewNotice}</p>}
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
