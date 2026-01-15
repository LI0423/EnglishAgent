import axios from 'axios';

const API_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const login = async (username, password) => {
  try {
    const response = await api.post('/auth/login', { username, password });
    if (response.data.access_token) {
      localStorage.setItem('user', JSON.stringify(response.data));
    }
    return response.data;
  } catch (error) {
    throw error.response?.data?.detail || 'Login failed';
  }
};

export const register = async (username, email, password) => {
  try {
    const response = await api.post('/auth/register', { username, email, password });
    if (response.data.access_token) {
      localStorage.setItem('user', JSON.stringify(response.data));
    }
    return response.data;
  } catch (error) {
    throw error.response?.data?.detail || 'Registration failed';
  }
};

export const registerPhone = async (phone, code) => {
  try {
    const response = await api.post('/auth/register/phone', { phone, code });
    if (response.data.access_token) {
      localStorage.setItem('user', JSON.stringify(response.data));
    }
    return response.data;
  } catch (error) {
    throw error.response?.data?.detail || 'Phone registration failed';
  }
};

export const getCurrentUser = async () => {
  const user = JSON.parse(localStorage.getItem('user'));
  if (!user || !user.access_token) {
    return null;
  }

  try {
    const response = await api.get('/auth/me', {
      headers: {
        'Authorization': `Bearer ${user.access_token}`,
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



export default api;
