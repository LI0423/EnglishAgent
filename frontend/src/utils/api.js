import axios from 'axios';

const normalizeApiUrl = (url) => String(url || '').trim().replace(/\/+$/, '');
const API_URL = normalizeApiUrl(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000');

const ERROR_MESSAGE_MAP = {
  'Invalid credentials': '账号或密码错误',
  'Missing token': '缺少登录凭证，请重新登录',
  'Invalid token': '登录凭证无效，请重新登录',
  'Invalid token subject': '登录凭证异常，请重新登录',
  'User not found': '用户不存在或已失效，请重新登录',
  'Username already exists': '用户名已存在',
  'Either username or phone is required': '请输入用户名或手机号',
  'Invalid or expired reset token': '重置凭证无效或已过期',
  'Unsupported reset channel': '不支持的重置方式',
  'Network Error': '网络异常，请检查后端服务是否已启动',
  'Failed to fetch': '网络连接失败，请稍后重试',
  'Request failed with status code 500': '服务异常（500），请稍后重试',
  'Request failed with status code 502': '网关异常（502），请稍后重试',
  'Request failed with status code 503': '服务不可用（503），请稍后重试',
  'timeout of 10000ms exceeded': '请求超时，请重试',
};

const translateErrorDetail = (message) => {
  const text = String(message || '').trim();
  if (!text) return '';
  return ERROR_MESSAGE_MAP[text] || text;
};

const normalizeFallback = (fallback) => {
  const translated = translateErrorDetail(fallback);
  return translated || '请求失败，请稍后重试';
};

export const normalizeUiError = (error, fallback = '请求失败，请稍后重试') => {
  const fallbackText = normalizeFallback(fallback);
  const raw = typeof error === 'string'
    ? error
    : (error?.userMessage || error?.response?.data?.detail || error?.message || fallbackText);
  const translated = translateErrorDetail(raw);
  if (translated && translated !== raw) return translated;
  const lower = String(raw || '').toLowerCase();
  if (!lower) return fallbackText;
  if (lower.includes('network error') || lower.includes('failed to fetch') || lower.includes('net::')) {
    return '网络异常，请检查后端服务是否已启动';
  }
  if (lower.includes('timeout')) {
    return '请求超时，请稍后重试';
  }
  if (lower.includes('invalid token') || lower.includes('missing token') || lower.includes('token subject')) {
    return '登录状态已失效，请重新登录';
  }
  return translated || fallbackText;
};

const getErrorDetail = (error, fallback = '请求失败，请稍后重试') => {
  return normalizeUiError(error, fallback);
};

const normalizeToken = (rawToken) => {
  const token = String(rawToken || '').trim();
  if (!token || token.toLowerCase() === 'undefined' || token.toLowerCase() === 'null') {
    return '';
  }
  if (token.startsWith('Bearer ')) {
    return token.slice(7).trim();
  }
  return token;
};

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const detail = String(error?.response?.data?.detail || '');
    if (status === 401 && /invalid token|missing token|token subject|user not found/i.test(detail)) {
      localStorage.removeItem('user');
      const message = '登录状态已失效，请重新登录';
      error.userMessage = message;
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:expired', { detail: { message } }));
      }
    }
    return Promise.reject(error);
  },
);

const getStoredToken = () => {
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    return normalizeToken(user?.access_token || user?.token || user?.data?.access_token || '');
  } catch {
    return '';
  }
};

export const login = async (usernameOrPhone, password) => {
  try {
    const account = String(usernameOrPhone || '').trim();
    const isPhone = /^1[3-9]\d{9}$/.test(account);
    const payload = isPhone
      ? { phone: account, password }
      : { username: account, password };
    const response = await api.post('/auth/login', payload);
    const accessToken = response.data.access_token || response.data.token;
    if (accessToken) {
      localStorage.setItem('user', JSON.stringify({ ...response.data, access_token: accessToken }));
    }
    return response.data;
  } catch (error) {
    throw getErrorDetail(error, '登录失败，请检查账号或密码');
  }
};

export const register = async (username, email, password) => {
  try {
    const response = await api.post('/auth/register', { username, email, password });
    const accessToken = response.data.access_token || response.data.token;
    if (accessToken) {
      localStorage.setItem('user', JSON.stringify({ ...response.data, access_token: accessToken }));
    }
    return response.data;
  } catch (error) {
    throw getErrorDetail(error, '注册失败');
  }
};

export const registerPhone = async (phone, password) => {
  try {
    const response = await api.post('/auth/register/phone', { phone, password });
    const accessToken = response.data?.data?.access_token || response.data?.access_token || response.data?.token;
    if (accessToken) {
      localStorage.setItem('user', JSON.stringify({ ...response.data, access_token: accessToken }));
    }
    return response.data;
  } catch (error) {
    throw getErrorDetail(error, '手机号注册失败');
  }
};

export const requestPasswordReset = async (account) => {
  try {
    const response = await api.post('/auth/password/reset/request', { account });
    return response.data;
  } catch (error) {
    throw getErrorDetail(error, '重置请求失败');
  }
};

export const confirmPasswordReset = async (resetToken, newPassword) => {
  try {
    const response = await api.post('/auth/password/reset/confirm', {
      reset_token: resetToken,
      new_password: newPassword,
    });
    return response.data;
  } catch (error) {
    throw getErrorDetail(error, '密码重置失败');
  }
};

export const requestPasswordResetCode = async (account, channel = 'email') => {
  try {
    const response = await api.post('/auth/password/reset/code/request', { account, channel });
    return response.data;
  } catch (error) {
    throw getErrorDetail(error, '验证码请求失败');
  }
};

export const confirmPasswordResetByCode = async (account, code, newPassword) => {
  try {
    const response = await api.post('/auth/password/reset/code/confirm', {
      account,
      code,
      new_password: newPassword,
    });
    return response.data;
  } catch (error) {
    throw getErrorDetail(error, '验证码重置失败');
  }
};

export const getCurrentUser = async () => {
  const token = getStoredToken();
  if (!token) {
    return null;
  }

  try {
    const response = await api.get('/auth/me', {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    return response.data;
  } catch {
    localStorage.removeItem('user');
    return null;
  }
};

export const logout = () => {
  localStorage.removeItem('user');
};

// 用户档案相关API
export const getProfile = async () => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    return null;
  }

  try {
    const response = await api.get('/profile/me', {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get profile:', error);
    return null;
  }
};

// 学习计划相关API
export const getPlans = async () => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    return [];
  }

  try {
    const response = await api.get('/plan', {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get plans:', error);
    return [];
  }
};

// 写作模块相关API
export const analyzeTask1Writing = async (text, chartType, topic, keywords = []) => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    throw new Error('Unauthorized');
  }

  try {
    const response = await api.post('/writing/task1/analyze', {
      text,
      chart_type: chartType,
      topic,
      keywords
    }, {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to analyze task 1 writing:', error);
    throw getErrorDetail(error, '分析失败');
  }
};

export const saveTask1Practice = async (text, chartType, topic, score = null) => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    throw new Error('Unauthorized');
  }

  try {
    const response = await api.post('/writing/task1/practice', {
      text,
      chart_type: chartType,
      topic,
      score
    }, {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to save task 1 practice:', error);
    throw getErrorDetail(error, '保存失败');
  }
};

export const getTask1Practices = async () => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    return [];
  }

  try {
    const response = await api.get('/writing/task1/practices', {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get task 1 practices:', error);
    return [];
  }
};

export const submitWritingPeerSubmission = async ({ taskType = 'task1', topic, content }) => {
  const response = await api.post('/writing/peer/submit', {
    task_type: taskType,
    topic,
    content,
  }, { headers: getAuthHeader() });
  return response.data;
};

export const getMyWritingPeerSubmissions = async (limit = 20) => {
  const response = await api.get('/writing/peer/submissions', {
    params: { limit },
    headers: getAuthHeader(),
  });
  return response.data || [];
};

export const claimWritingPeerSubmission = async () => {
  const response = await api.post('/writing/peer/claim', {}, { headers: getAuthHeader() });
  return response.data;
};

export const submitWritingPeerReview = async (payload) => {
  const response = await api.post('/writing/peer/review', payload, { headers: getAuthHeader() });
  return response.data;
};

export const getWritingPeerReviewAssist = async (payload = {}) => {
  const response = await api.post('/writing/peer/review/assist', payload, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getReceivedWritingPeerReviews = async (submissionId = null, limit = 30) => {
  const response = await api.get('/writing/peer/reviews/received', {
    params: { submission_id: submissionId, limit },
    headers: getAuthHeader(),
  });
  return response.data || [];
};

export const getWritingPeerStats = async () => {
  const response = await api.get('/writing/peer/stats', {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getWritingPeerLeaderboard = async (limit = 10) => {
  const response = await api.get('/writing/peer/leaderboard', {
    params: { limit },
    headers: getAuthHeader(),
  });
  return response.data || [];
};

export const getTask1CommonStructures = async () => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    return [];
  }

  try {
    const response = await api.get('/writing/task1/common-structures', {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get task 1 common structures:', error);
    return [];
  }
};

export const getTask1CommonVocabulary = async () => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    return [];
  }

  try {
    const response = await api.get('/writing/task1/common-vocabulary', {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get task 1 common vocabulary:', error);
    return [];
  }
};

// 获取计划任务列表
export const getPlanTasks = async (planId) => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    return [];
  }

  try {
    const response = await api.get(`/plan/${planId}/tasks`, {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get plan tasks:', error);
    return [];
  }
};

// 获取统计概览
export const getStatsOverview = async (timeRange = 86400) => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    return null;
  }

  try {
    const response = await api.get('/stats/overview', {
      params: { time_range: timeRange },
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get stats overview:', error);
    return null;
  }
};


// 错题管理API
const getAuthHeader = () => {
  const token = getStoredToken();
  if (!token) {
    throw new Error('登录状态已失效，请重新登录');
  }
  return { Authorization: `Bearer ${token}` };
};

export const getMistakes = async (
  module = null,
  limit = 50,
  questionType = null,
  errorType = null,
  createdFrom = null,
  createdTo = null,
  nextReviewFrom = null,
  nextReviewTo = null,
) => {
  try {
    const response = await api.get('/mistakes', {
      params: {
        module,
        limit,
        question_type: questionType,
        error_type: errorType,
        created_from: createdFrom,
        created_to: createdTo,
        next_review_from: nextReviewFrom,
        next_review_to: nextReviewTo,
      },
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get mistakes:', error);
    return [];
  }
};

export const createMistake = async (payload) => {
  const response = await api.post('/mistakes', payload, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const reviewMistake = async (mistakeId, masteryDelta = 0.2) => {
  const response = await api.post(`/mistakes/${mistakeId}/review`, null, {
    params: { mastery_delta: masteryDelta },
    headers: getAuthHeader(),
  });
  return response.data;
};

export const batchReviewMistakes = async (mistakeIds = [], masteryDelta = 0.2) => {
  const response = await api.post('/mistakes/review/batch', {
    mistake_ids: mistakeIds,
    mastery_delta: masteryDelta,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getMistakeStats = async () => {
  try {
    const response = await api.get('/mistakes/stats/summary', {
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get mistake stats:', error);
    return { total: 0, by_module: {} };
  }
};

export const getDueMistakes = async (module = null, limit = 50, questionType = null) => {
  try {
    const response = await api.get('/mistakes/due', {
      params: { module, limit, question_type: questionType },
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get due mistakes:', error);
    return [];
  }
};

export const getMistakeAnalysis = async () => {
  try {
    const response = await api.get('/mistakes/analysis', {
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get mistake analysis:', error);
    return {
      total: 0,
      due_count: 0,
      avg_mastery: 0,
      by_error_type: {},
      by_difficulty: {},
      by_question_type: {},
      by_error_and_question_type: {},
      vocabulary_test_wrong_count: 0,
      vocabulary_test_wrong_ratio: 0,
    };
  }
};

export const getMistakeReviewQueue = async (
  module = null,
  limit = 30,
  questionType = null,
  nextReviewFrom = null,
  nextReviewTo = null,
) => {
  try {
    const response = await api.get('/mistakes/review-queue', {
      params: {
        module,
        limit,
        question_type: questionType,
        next_review_from: nextReviewFrom,
        next_review_to: nextReviewTo,
      },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get mistake review queue:', error);
    return [];
  }
};

export const getMistakeClusters = async (module = null, limit = 20, questionType = null) => {
  try {
    const response = await api.get('/mistakes/clusters', {
      params: { module, limit, question_type: questionType },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get mistake clusters:', error);
    return [];
  }
};

export const getMistakeTrends = async (days = 7, module = null, questionType = null) => {
  try {
    const response = await api.get('/mistakes/trends', {
      params: { days, module, question_type: questionType },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get mistake trends:', error);
    return [];
  }
};

export const getMistakeReviewEffectiveness = async (days = 7, module = null, questionType = null) => {
  try {
    const response = await api.get('/mistakes/review-effectiveness', {
      params: { days, module, question_type: questionType },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get mistake review effectiveness:', error);
    return [];
  }
};

export const getMistakeHotspots = async (days = 14, module = null, limit = 30) => {
  try {
    const response = await api.get('/mistakes/hotspots', {
      params: { days, module, limit },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get mistake hotspots:', error);
    return [];
  }
};

export const getMistakeRecommendations = async (days = 14, module = null, limit = 5) => {
  try {
    const response = await api.get('/mistakes/recommendations', {
      params: { days, module, limit },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get mistake recommendations:', error);
    return [];
  }
};

export const getMistakeModuleComparison = async (days = 14) => {
  try {
    const response = await api.get('/mistakes/module-comparison', {
      params: { days },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get mistake module comparison:', error);
    return [];
  }
};

export const getMistakeWeeklyFocus = async (days = 14, totalDailyMinutes = 90) => {
  try {
    const response = await api.get('/mistakes/weekly-focus', {
      params: { days, total_daily_minutes: totalDailyMinutes },
      headers: getAuthHeader(),
    });
    return response.data || null;
  } catch (error) {
    console.error('Failed to get mistake weekly focus:', error);
    return null;
  }
};

export const exportMistakes = async (format = 'json', module = null, limit = 1000, questionType = null, errorType = null) => {
  const response = await api.get('/mistakes/export', {
    params: { format, module, limit, question_type: questionType, error_type: errorType },
    headers: getAuthHeader(),
    responseType: format === 'csv' ? 'text' : 'json',
  });
  return response.data;
};

export const importMistakes = async (items = []) => {
  const response = await api.post('/mistakes/import', { items }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

// 词汇学习API
export const getVocabularyList = async (limit = 100, { sourceModule = null, tag = null, keyword = null } = {}) => {
  try {
    const response = await api.get('/vocabulary', {
      params: {
        limit,
        source_module: sourceModule,
        tag,
        keyword,
      },
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get vocabulary list:', error);
    return [];
  }
};

export const addVocabularyWord = async (payload) => {
  const response = await api.post('/vocabulary/add', payload, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const startVocabularySession = async (strategy = 'spaced', count = 10) => {
  const response = await api.post('/vocabulary/learn/session', {
    strategy,
    count,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getDueVocabulary = async (limit = 100) => {
  try {
    const response = await api.get('/vocabulary/due', {
      params: { limit },
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get due vocabulary:', error);
    return [];
  }
};

export const reviewVocabularyWord = async (vocabId, masteryDelta = 0.15) => {
  const response = await api.post(`/vocabulary/${vocabId}/review`, null, {
    params: { mastery_delta: masteryDelta },
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getVocabularyStats = async () => {
  try {
    const response = await api.get('/vocabulary/stats/summary', {
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get vocabulary stats:', error);
    return { total: 0, due_count: 0, avg_mastery: 0, by_source_module: {} };
  }
};

export const getVocabularyStrategyInsights = async (days = 14) => {
  try {
    const response = await api.get('/vocabulary/strategy/insights', {
      params: { days },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get vocabulary strategy insights:', error);
    return [];
  }
};

export const generateVocabularyTest = async (mode = 'multiple_choice', count = 5) => {
  const response = await api.post('/vocabulary/test/generate', {
    mode,
    count,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const submitVocabularyTest = async (testId, answers = []) => {
  const response = await api.post('/vocabulary/test/submit', {
    test_id: testId,
    answers,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getPrioritizedWrongReviewQueue = async (wordIds = [], limit = 30) => {
  if (!Array.isArray(wordIds) || wordIds.length === 0) {
    return [];
  }
  const response = await api.post('/vocabulary/wrong/review-queue', {
    word_ids: wordIds,
    limit,
  }, {
    headers: getAuthHeader(),
  });
  return response.data || [];
};

export const getVocabularyScenarios = async (module = null, topic = null) => {
  try {
    const response = await api.get('/vocabulary/scenarios', {
      params: { module, topic },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    throw getErrorDetail(error, '加载场景词包失败');
  }
};

export const importVocabularyScenario = async (module, topic, limit = 20, sourceModule = 'scenario_pack') => {
  try {
    const response = await api.post('/vocabulary/scenarios/import', {
      module,
      topic,
      limit,
      source_module: sourceModule,
    }, {
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    throw getErrorDetail(error, '导入场景词包失败');
  }
};

export const autoCollectVocabulary = async (text, sourceModule = 'reading', topic = 'general', maxWords = 20) => {
  const response = await api.post('/vocabulary/collect', {
    text,
    source_module: sourceModule,
    topic,
    max_words: maxWords,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const generateContextReplay = async ({
  count = 5,
  sourceModule = null,
  topic = null,
  mode = 'cloze',
  wordIds = [],
} = {}) => {
  const response = await api.post('/vocabulary/context/replay/generate', {
    count,
    source_module: sourceModule,
    topic,
    mode,
    word_ids: wordIds,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const submitContextReplay = async (sessionId, answers = []) => {
  const response = await api.post('/vocabulary/context/replay/submit', {
    session_id: sessionId,
    answers,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getContextReplayRetryQueue = async (limit = 30) => {
  const response = await api.get('/vocabulary/context/replay/retry-queue', {
    params: { limit },
    headers: getAuthHeader(),
  });
  return response.data || [];
};

export const postChatMessage = async (
  query,
  sessionId,
  {
    enableAgenticRag = false,
    ragConfig = null,
  } = {},
) => {
  try {
    const response = await api.post('/chat/', {
      query,
      session_id: sessionId,
      enable_agentic_rag: enableAgenticRag,
      rag_config: ragConfig,
    }, {
      headers: getAuthHeader(),
    });
    return response.data;
  } catch (error) {
    if (error?.response?.status === 401) {
      localStorage.removeItem('user');
      throw '登录状态已失效，请重新登录。';
    }
    throw normalizeUiError(error, '请求失败，请稍后重试');
  }
};

export const getChatSessions = async (limit = 30) => {
  try {
    const response = await api.get('/chat/history/sessions', {
      params: { limit },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get chat sessions:', error);
    return [];
  }
};

export const getChatHistory = async (sessionId, limit = 200) => {
  try {
    const response = await api.get(`/chat/history/${sessionId}`, {
      params: { limit },
      headers: getAuthHeader(),
    });
    return response.data || [];
  } catch (error) {
    console.error('Failed to get chat history:', error);
    return [];
  }
};

// 听力模块 API
export const getListeningLibrary = async () => {
  const response = await api.get('/listening/library', { headers: getAuthHeader() });
  return response.data;
};

export const getListeningLibraryVersion = async () => {
  const response = await api.get('/listening/library/version', { headers: getAuthHeader() });
  return response.data;
};

export const getListeningQuizVersion = async () => {
  const response = await api.get('/listening/quiz/version', { headers: getAuthHeader() });
  return response.data;
};

export const generateListeningQuiz = async ({ count = 5, difficulty = null, audioId = null } = {}) => {
  const response = await api.post('/listening/quiz/generate', {
    count,
    difficulty,
    audio_id: audioId,
  }, { headers: getAuthHeader() });
  return response.data;
};

export const submitListeningQuiz = async (quizId, answers = []) => {
  const response = await api.post('/listening/quiz/submit', {
    quiz_id: quizId,
    answers,
  }, { headers: getAuthHeader() });
  return response.data;
};

export const getListeningStatus = async () => {
  const response = await api.get('/listening/status', { headers: getAuthHeader() });
  return response.data;
};

export const startListening = async (audioId, currentTime = 0) => {
  const response = await api.post('/listening/start', {
    audio_id: audioId,
    current_time: currentTime,
  }, { headers: getAuthHeader() });
  return response.data;
};

export const pauseListening = async (currentTime = null) => {
  const response = await api.post('/listening/pause', {
    current_time: currentTime,
  }, { headers: getAuthHeader() });
  return response.data;
};

export const resumeListening = async (currentTime = null) => {
  const response = await api.post('/listening/resume', {
    current_time: currentTime,
  }, { headers: getAuthHeader() });
  return response.data;
};

export const stopListening = async () => {
  const response = await api.post('/listening/stop', {}, { headers: getAuthHeader() });
  return response.data;
};

export const setListeningSpeed = async (speed) => {
  const response = await api.post('/listening/set-speed', {
    speed,
  }, { headers: getAuthHeader() });
  return response.data;
};

// 阅读模块 API
export const analyzeReadingPassage = async (text) => {
  const response = await api.post('/reading/analyze', { text }, { headers: getAuthHeader() });
  return response.data;
};

export const detectReadingSynonyms = async (text, topic = 'general') => {
  const response = await api.post('/reading/synonyms', { text, topic }, { headers: getAuthHeader() });
  return response.data;
};

export const analyzeReadingLongSentences = async (text) => {
  const response = await api.post('/reading/long-sentences', { text }, { headers: getAuthHeader() });
  return response.data;
};

export const getReadingQuizVersion = async () => {
  const response = await api.get('/reading/quiz/version', { headers: getAuthHeader() });
  return response.data;
};

export const generateReadingQuiz = async ({ count = 5, difficulty = null, questionType = null } = {}) => {
  const response = await api.post('/reading/quiz/generate', {
    count,
    difficulty,
    question_type: questionType,
  }, { headers: getAuthHeader() });
  return response.data;
};

export const submitReadingQuiz = async (quizId, answers = []) => {
  const response = await api.post('/reading/quiz/submit', {
    quiz_id: quizId,
    answers,
  }, { headers: getAuthHeader() });
  return response.data;
};

// 口语模块 API
export const createSpeakingSession = async () => {
  const response = await api.post('/speaking/session', {}, { headers: getAuthHeader() });
  return response.data;
};

export const listSpeakingSessions = async (limit = 20, offset = 0) => {
  const response = await api.get('/speaking/sessions', {
    params: { limit, offset },
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getSpeakingSession = async (sessionId) => {
  const response = await api.get(`/speaking/session/${sessionId}`, { headers: getAuthHeader() });
  return response.data;
};

export const startSpeakingPart = async (sessionId, partIndex) => {
  const response = await api.post(`/speaking/session/${sessionId}/part/${partIndex}/start`, {}, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const uploadSpeakingText = async (sessionId, textPartial) => {
  const response = await api.post(`/speaking/session/${sessionId}/audio`, {
    textPartial,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const submitSpeakingTurn = async (sessionId, userText, { mode = 'coach', partIndex = null } = {}) => {
  const response = await api.post(`/speaking/session/${sessionId}/turn`, {
    userText,
    mode,
    partIndex,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const summarizeSpeakingSession = async (sessionId) => {
  const response = await api.post(`/speaking/session/${sessionId}/summary`, {}, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const finishSpeakingSession = async (sessionId) => {
  const response = await api.post(`/speaking/session/${sessionId}/finish`, {}, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const scoreSpeaking = async (transcriptId, audioUrl = null) => {
  const response = await api.post('/scoring/speaking', {
    transcriptId,
    audioUrl,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

// 报告 API
export const getSessionReport = async (sessionId) => {
  const response = await api.get(`/report/${sessionId}`, { headers: getAuthHeader() });
  return response.data;
};

export const getPlanHealthReport = async (planId = null, days = 14) => {
  const response = await api.get('/report/plan/health', {
    params: { plan_id: planId, days },
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getPlanCalibrationLogs = async (planId = null, limit = 20) => {
  const response = await api.get('/report/plan/calibrations', {
    params: { plan_id: planId, limit },
    headers: getAuthHeader(),
  });
  return response.data || [];
};

export const getPlanInterventionStatus = async (planId = null, days = 14) => {
  const response = await api.get('/report/plan/intervention-status', {
    params: { plan_id: planId, days },
    headers: getAuthHeader(),
  });
  return response.data || null;
};

// 计划 API
export const generatePlan7d = async (weaknesses = [], targetScore = 7.0, dailyTimeAvailable = '1-2 hours') => {
  const response = await api.post('/plan/7d', {
    weaknesses,
    target_score: targetScore,
    daily_time_available: dailyTimeAvailable,
  }, {
    headers: getAuthHeader(),
  });
  return response.data;
};

export const createLearningPlan = async (payload) => {
  const response = await api.post('/plan/create', payload, { headers: getAuthHeader() });
  return response.data;
};

export const getLearningPlanDetail = async (planId) => {
  const response = await api.get(`/plan/${planId}`, { headers: getAuthHeader() });
  return response.data;
};

export const generateWeeklyPlanTasks = async (planId, days = 7) => {
  const response = await api.post(
    `/plan/${planId}/tasks/generate-weekly`,
    { days },
    { headers: getAuthHeader() },
  );
  return response.data;
};

export const getLearningPlanTasks = async (planId) => {
  const response = await api.get(`/plan/${planId}/tasks`, { headers: getAuthHeader() });
  return response.data || [];
};

export const getLearningPlanProgress = async (planId) => {
  const response = await api.get(`/plan/${planId}/progress`, { headers: getAuthHeader() });
  return response.data || null;
};

export const updatePlanTaskProgress = async (dailyTaskId, payload) => {
  const response = await api.put(`/plan/tasks/${dailyTaskId}/progress`, payload, { headers: getAuthHeader() });
  return response.data;
};

export const updateLearningPlanSettings = async (planId, payload) => {
  const response = await api.put(`/plan/${planId}/settings`, payload, { headers: getAuthHeader() });
  return response.data;
};

export const getPlanInterventionPreview = async (planId, days = 14, remedialDays = 3) => {
  const response = await api.get(`/plan/${planId}/intervention/preview`, {
    params: { days, remedial_days: remedialDays },
    headers: getAuthHeader(),
  });
  return response.data;
};

export const applyPlanIntervention = async (planId, days = 14, remedialDays = 3) => {
  const response = await api.post(
    `/plan/${planId}/intervention/apply`,
    { days, remedial_days: remedialDays },
    { headers: getAuthHeader() },
  );
  return response.data;
};

// 诊断模块 API
export const startDiagnostic = async (modules = ['listening', 'reading', 'writing', 'speaking']) => {
  const response = await api.post('/diagnostic/start', { modules }, { headers: getAuthHeader() });
  return response.data;
};

export const submitDiagnosticAnswers = async (sessionId, answers = []) => {
  const response = await api.post(`/diagnostic/${sessionId}/answer`, { answers }, { headers: getAuthHeader() });
  return response.data;
};

export const getDiagnosticReport = async (sessionId) => {
  const response = await api.get(`/diagnostic/${sessionId}/report`, { headers: getAuthHeader() });
  return response.data;
};

export const completeDiagnostic = async (sessionId) => {
  const response = await api.post(`/diagnostic/${sessionId}/complete`, {}, { headers: getAuthHeader() });
  return response.data;
};

export const getDiagnosticHistorySummary = async (limit = 10) => {
  const response = await api.get('/diagnostic/history/summary', {
    params: { limit },
    headers: getAuthHeader(),
  });
  return response.data;
};

export const getDiagnosticBankVersion = async () => {
  const response = await api.get('/diagnostic/bank/version', { headers: getAuthHeader() });
  return response.data;
};

export const getDiagnosticBankHealth = async () => {
  const response = await api.get('/diagnostic/bank/health', { headers: getAuthHeader() });
  return response.data;
};

export const reloadDiagnosticBank = async () => {
  const response = await api.post('/diagnostic/bank/reload', {}, { headers: getAuthHeader() });
  return response.data;
};

export default api;
