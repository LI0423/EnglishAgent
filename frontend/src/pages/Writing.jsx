import { useEffect, useState, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { getCurrentUser } from '../utils/api';
import { analyzeTask1Writing, saveTask1Practice } from '../utils/api';

const Writing = () => {
  const navItems = [
    { to: '/', label: '🏠 首页' },
    { to: '/chat', label: '🤖 智能对话' },
    { to: '/listening', label: '🎧 听力练习' },
    { to: '/reading', label: '📚 阅读练习' },
    { to: '/writing', label: '📝 写作练习' },
    { to: '/speaking', label: '💬 口语练习' },
    { to: '/vocabulary', label: '📋 词汇学习' },
    { to: '/mistakes', label: '🔖 错题本' },
    { to: '/mock-exam', label: '🎯 模拟考试' },
    { to: '/reports', label: '📊 学习报告' },
    { to: '/profile', label: '👤 个人中心' },
  ];

  const [userData, setUserData] = useState({ username: '李同学' });
  const [writingContent, setWritingContent] = useState('');
  const [wordCount, setWordCount] = useState(0);
  const [timeRemaining, setTimeRemaining] = useState(40 * 60); // 40分钟
  const [taskType, setTaskType] = useState('task1');
  const [aiFeedback, setAiFeedback] = useState({});
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const timerRef = useRef(null);

  // 获取用户数据
  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const user = await getCurrentUser();
        if (user) {
          setUserData(prev => ({ ...prev, username: user.username }));
        }
      } catch (err) {
        console.error('Failed to fetch user data:', err);
      }
    };

    fetchUserData();
  }, []);

  // 初始化倒计时
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setTimeRemaining(prev => {
        if (prev <= 0) {
          clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  // 实时字数统计
  useEffect(() => {
    const count = writingContent.trim().split(/\s+/).filter(word => word.length > 0).length;
    setWordCount(count);
  }, [writingContent]);

  // 模拟题目数据
  const task1Question = {
    title: '图表写作：2023年不同城市旅游人数',
    chartType: '柱状图',
    requirements: '总结图表中的主要信息，比较数据并提供相关见解，至少150词。',
    exampleImage: '📊'
  };

  // 处理写作内容变化
  const handleContentChange = (e) => {
    setWritingContent(e.target.value);
  };

  // 保存草稿
  const handleSaveDraft = async () => {
    if (!writingContent.trim()) return;

    setSaving(true);
    try {
      await saveTask1Practice(
        writingContent,
        task1Question.chartType,
        task1Question.title
      );
      alert('草稿保存成功！');
    } catch (error) {
      console.error('Failed to save draft:', error);
      alert('保存失败，请重试！');
    } finally {
      setSaving(false);
    }
  };

  // 提交写作
  const handleSubmit = async () => {
    if (!writingContent.trim()) return;

    setSubmitting(true);
    try {
      // 分析写作内容
      const analysis = await analyzeTask1Writing(
        writingContent,
        task1Question.chartType,
        task1Question.title
      );
      
      if (analysis) {
        setAiFeedback(analysis);
        alert('提交成功，已生成AI反馈！');
      }

      // 保存写作练习
      await saveTask1Practice(
        writingContent,
        task1Question.chartType,
        task1Question.title,
        analysis?.total_score
      );
    } catch (error) {
      console.error('Failed to submit writing:', error);
      alert('提交失败，请重试！');
    } finally {
      setSubmitting(false);
    }
  };

  // 格式化文本
  const handleFormat = () => {
    // 简单的格式化功能，实际项目中可以使用更复杂的富文本编辑器
    const formatted = writingContent
      .replace(/\n\n+/g, '\n\n') // 去除多余空行
      .replace(/^\s+/gm, '') // 去除每行开头空格
      .trim();
    setWritingContent(formatted);
  };

  // 重置写作区域
  const handleReset = () => {
    if (confirm('确定要清空写作内容吗？')) {
      setWritingContent('');
      setAiFeedback({});
    }
  };

  // 格式化时间显示
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="writing-page">
      {/* 顶部导航栏 */}
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left">
            <h1>🎓 IELTS Agent</h1>
          </div>
          <div className="nav-right">
            <div className="notification">
              <span className="icon">🔔</span>
              <span className="badge">3</span>
            </div>
            <div className="user-profile">
              <span className="avatar">👤</span>
              <span className="username">{userData.username}</span>
            </div>
            <div className="settings">
              <span className="icon">⚙️</span>
            </div>
          </div>
        </div>
      </header>

      {/* 主要内容布局 */}
      <div className="main-layout">
        {/* 左侧导航栏 */}
        <div className="sidebar">
          <div className="sidebar-header">
            <h2>🎓 IELTS Agent</h2>
          </div>
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

        {/* 右侧内容区 */}
        <div className="content-area">
          <main className="writing-content">
            {/* 页面标题和面包屑导航 */}
            <div className="page-header">
              <div className="breadcrumb">
                <span>首页</span> &gt; <span>写作练习</span>
              </div>
              <h1 className="page-title">📝 写作练习</h1>
            </div>

            {/* 任务类型切换 */}
            <div className="task-type-switch">
              <button 
                className={`task-btn ${taskType === 'task1' ? 'active' : ''}`}
                onClick={() => setTaskType('task1')}
              >
                Task 1
              </button>
              <button 
                className={`task-btn ${taskType === 'task2' ? 'active' : ''}`}
                onClick={() => setTaskType('task2')}
              >
                Task 2
              </button>
            </div>

            {/* 题目展示区 */}
            <div className="question-section">
              <div className="question-card">
                <h2 className="question-title">{task1Question.title}</h2>
                <div className="chart-placeholder">{task1Question.exampleImage}</div>
                <div className="question-requirements">
                  <h3>写作要求：</h3>
                  <p>{task1Question.requirements}</p>
                </div>
              </div>

              {/* AI反馈区 */}
              <div className="ai-feedback-card">
                <h3>📝 AI反馈</h3>
                {Object.keys(aiFeedback).length > 0 ? (
                  <div className="feedback-content">
                    {aiFeedback.feedback && aiFeedback.feedback.length > 0 && (
                      <div className="feedback-list">
                        {aiFeedback.feedback.map((item, index) => (
                          <div key={index} className={`feedback-item ${item.severity === 'high' ? 'error' : 'warning'}`}>
                            <span className="feedback-icon">{item.severity === 'high' ? '❌' : '⚠️'}</span>
                            <span className="feedback-message">{item.message}</span>
                            {item.suggestion && (
                              <span className="feedback-suggestion">建议：{item.suggestion}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {aiFeedback.total_score && (
                      <div className="score-section">
                        <h4>总分：<span className="score-value">{aiFeedback.total_score}/9</span></h4>
                        <div className="score-details">
                          <div className="score-item">
                            <span>结构：{aiFeedback.structure_score}/9</span>
                          </div>
                          <div className="score-item">
                            <span>内容：{aiFeedback.content_score}/9</span>
                          </div>
                          <div className="score-item">
                            <span>词汇：{aiFeedback.vocabulary_score}/9</span>
                          </div>
                          <div className="score-item">
                            <span>语法：{aiFeedback.grammar_score}/9</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="no-feedback">
                    <p>开始写作，AI将为您提供实时反馈</p>
                  </div>
                )}
              </div>
            </div>

            {/* 写作区域 */}
            <div className="writing-section">
              <div className="writing-header">
                <div className="writing-info">
                  <div className="timer">⏱️ {formatTime(timeRemaining)}</div>
                  <div className={`word-count ${wordCount >= 150 ? 'target-reached' : ''}`}>
                    字数：{wordCount}/150
                  </div>
                </div>
                
                {/* 工具栏 */}
                <div className="writing-toolbar">
                  <button 
                    className="toolbar-btn save-btn"
                    onClick={handleSaveDraft}
                    disabled={saving || !writingContent.trim()}
                  >
                    {saving ? '保存中...' : '💾 保存草稿'}
                  </button>
                  <button 
                    className="toolbar-btn format-btn"
                    onClick={handleFormat}
                    disabled={!writingContent.trim()}
                  >
                    📋 格式化
                  </button>
                  <button 
                    className="toolbar-btn reset-btn"
                    onClick={handleReset}
                    disabled={!writingContent.trim()}
                  >
                    🔄 重置
                  </button>
                  <button 
                    className="toolbar-btn submit-btn"
                    onClick={handleSubmit}
                    disabled={submitting || !writingContent.trim() || wordCount < 150}
                  >
                    {submitting ? '提交中...' : '📤 提交练习'}
                  </button>
                </div>
              </div>

              {/* 写作输入框 */}
              <div className="writing-input-container">
                <textarea
                  className="writing-textarea"
                  placeholder="请在此输入您的作文内容..."
                  value={writingContent}
                  onChange={handleContentChange}
                  rows={20}
                ></textarea>
              </div>
            </div>

            {/* 词汇建议 */}
            <div className="vocabulary-suggestions">
              <h3>💡 词汇建议</h3>
              <div className="suggestions-list">
                <div className="suggestion-item">
                  <span className="original-word">significant</span>
                  <span className="suggested-words">→ varies substantially, differs greatly</span>
                </div>
                <div className="suggestion-item">
                  <span className="original-word">increase</span>
                  <span className="suggested-words">→ rise, grow, surge</span>
                </div>
                <div className="suggestion-item">
                  <span className="original-word">decrease</span>
                  <span className="suggested-words">→ fall, decline, drop</span>
                </div>
                <div className="suggestion-item">
                  <span className="original-word">show</span>
                  <span className="suggested-words">→ demonstrate, indicate, reveal</span>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default Writing;
