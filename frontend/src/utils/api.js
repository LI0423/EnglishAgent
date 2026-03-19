import axios from 'axios';

const API_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const getStoredToken = () => {
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    return user?.access_token || user?.token || user?.data?.access_token || '';
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
    throw error.response?.data?.detail || 'Login failed';
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
    throw error.response?.data?.detail || 'Registration failed';
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
    throw error.response?.data?.detail || 'Phone registration failed';
  }
};

export const requestPasswordReset = async (account) => {
  try {
    const response = await api.post('/auth/password/reset/request', { account });
    return response.data;
  } catch (error) {
    throw error.response?.data?.detail || 'Password reset request failed';
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
    throw error.response?.data?.detail || 'Password reset failed';
  }
};

export const requestPasswordResetCode = async (account, channel = 'email') => {
  try {
    const response = await api.post('/auth/password/reset/code/request', { account, channel });
    return response.data;
  } catch (error) {
    throw error.response?.data?.detail || 'Verification code request failed';
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
    throw error.response?.data?.detail || 'Password reset by code failed';
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
    throw error.response?.data?.detail || 'Analysis failed';
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
    throw error.response?.data?.detail || 'Save failed';
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

export const getMistakes = async (module = null, limit = 50, questionType = null) => {
  try {
    const response = await api.get('/mistakes', {
      params: { module, limit, question_type: questionType },
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

export const exportMistakes = async (format = 'json', module = null, limit = 1000, questionType = null) => {
  const response = await api.get('/mistakes/export', {
    params: { format, module, limit, question_type: questionType },
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
export const getVocabularyList = async (limit = 100) => {
  try {
    const response = await api.get('/vocabulary', {
      params: { limit },
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
    throw error?.response?.data?.detail || error?.message || '请求失败，请稍后重试。';
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
