import { useEffect, useState, useRef } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { getCurrentUser } from '../utils/api';
import {
  analyzeTask1Writing,
  claimWritingPeerSubmission,
  getMyWritingPeerSubmissions,
  getReceivedWritingPeerReviews,
  saveTask1Practice,
  submitWritingPeerReview,
  submitWritingPeerSubmission,
} from '../utils/api';

const Writing = () => {
  const location = useLocation();
  const navigate = useNavigate();
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
  const [replayNotice, setReplayNotice] = useState('');
  const [peerTopic, setPeerTopic] = useState('Task 1 图表描述练习');
  const [peerSubmitting, setPeerSubmitting] = useState(false);
  const [peerClaimed, setPeerClaimed] = useState(null);
  const [peerReviewing, setPeerReviewing] = useState(false);
  const [peerMySubs, setPeerMySubs] = useState([]);
  const [peerReceived, setPeerReceived] = useState([]);
  const [peerTR, setPeerTR] = useState(6);
  const [peerCC, setPeerCC] = useState(6);
  const [peerLR, setPeerLR] = useState(6);
  const [peerGRA, setPeerGRA] = useState(6);
  const [peerStrengths, setPeerStrengths] = useState('');
  const [peerImprovements, setPeerImprovements] = useState('');
  const [peerComment, setPeerComment] = useState('');
  const [peerMessage, setPeerMessage] = useState('');
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

  const loadPeerData = async () => {
    try {
      const [subs, received] = await Promise.all([
        getMyWritingPeerSubmissions(20),
        getReceivedWritingPeerReviews(null, 20),
      ]);
      setPeerMySubs(subs || []);
      setPeerReceived(received || []);
    } catch (err) {
      console.error('Failed to load peer data:', err);
    }
  };

  // 实时字数统计
  useEffect(() => {
    const count = writingContent.trim().split(/\s+/).filter(word => word.length > 0).length;
    setWordCount(count);
  }, [writingContent]);

  useEffect(() => {
    const params = new URLSearchParams(location.search || '');
    if (params.get('replay') !== '1') return;
    const qType = (params.get('questionType') || '').toLowerCase();
    const questionId = params.get('questionId') || '';
    if (qType === 'writing_task1') {
      setTaskType('task1');
    }
    setReplayNotice(questionId ? `来自错题重练：题目 ${questionId}` : '来自错题重练：建议先完成一篇写作练习');
  }, [location.search]);

  useEffect(() => {
    loadPeerData();
  }, []);

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

  const handlePeerSubmit = async () => {
    if (!writingContent.trim() || writingContent.trim().length < 30) return;
    setPeerSubmitting(true);
    setPeerMessage('');
    try {
      const res = await submitWritingPeerSubmission({
        taskType: taskType === 'task2' ? 'task2' : 'task1',
        topic: peerTopic.trim() || 'Writing peer review',
        content: writingContent.trim(),
      });
      setPeerMessage(res?.message || '已提交到互评池');
      await loadPeerData();
    } catch (err) {
      setPeerMessage(typeof err === 'string' ? err : '互评投稿失败');
    } finally {
      setPeerSubmitting(false);
    }
  };

  const handlePeerClaim = async () => {
    setPeerMessage('');
    try {
      const res = await claimWritingPeerSubmission();
      if (res?.claimed && res?.submission) {
        setPeerClaimed(res.submission);
      } else {
        setPeerClaimed(null);
      }
      setPeerMessage(res?.message || '');
    } catch (err) {
      setPeerMessage(typeof err === 'string' ? err : '领取互评任务失败');
    }
  };

  const handlePeerReviewSubmit = async () => {
    if (!peerClaimed?.id) return;
    setPeerReviewing(true);
    setPeerMessage('');
    try {
      const res = await submitWritingPeerReview({
        submission_id: peerClaimed.id,
        tr_score: Number(peerTR),
        cc_score: Number(peerCC),
        lr_score: Number(peerLR),
        gra_score: Number(peerGRA),
        strengths: peerStrengths,
        improvements: peerImprovements,
        comment_text: peerComment,
      });
      setPeerMessage(`互评提交成功（质量等级：${res?.quality_tier || 'basic'}）`);
      setPeerClaimed(null);
      setPeerStrengths('');
      setPeerImprovements('');
      setPeerComment('');
      await loadPeerData();
    } catch (err) {
      setPeerMessage(typeof err === 'string' ? err : '提交互评失败');
    } finally {
      setPeerReviewing(false);
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
            {replayNotice && (
              <div className="card" style={{ marginBottom: 16, borderColor: '#7bb5ff', background: '#f3f8ff' }}>
                <h3>错题重练指引</h3>
                <p>{replayNotice}</p>
                <button onClick={() => navigate('/mistakes?module=writing&questionType=writing_task1')}>返回错题本</button>
              </div>
            )}
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

            <div className="card" style={{ marginTop: 16 }}>
              <h3>🤝 作文互评 1.0</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
                <input
                  value={peerTopic}
                  onChange={(e) => setPeerTopic(e.target.value)}
                  placeholder="互评题目标题"
                  style={{ minWidth: 260 }}
                />
                <button onClick={handlePeerSubmit} disabled={peerSubmitting || !writingContent.trim() || writingContent.trim().length < 30}>
                  {peerSubmitting ? '投稿中...' : '投递当前作文到互评池'}
                </button>
                <button onClick={handlePeerClaim}>领取一篇互评任务</button>
              </div>
              {peerMessage && <p style={{ color: '#0f766e' }}>{peerMessage}</p>}

              {peerClaimed && (
                <div style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: 10, marginBottom: 10 }}>
                  <p><strong>待互评作文：</strong>{peerClaimed.topic}（{peerClaimed.task_type}）</p>
                  <p style={{ maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{peerClaimed.content}</p>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                    <label>TR <input type="number" min="0" max="9" step="0.5" value={peerTR} onChange={(e) => setPeerTR(e.target.value)} style={{ width: 70 }} /></label>
                    <label>CC <input type="number" min="0" max="9" step="0.5" value={peerCC} onChange={(e) => setPeerCC(e.target.value)} style={{ width: 70 }} /></label>
                    <label>LR <input type="number" min="0" max="9" step="0.5" value={peerLR} onChange={(e) => setPeerLR(e.target.value)} style={{ width: 70 }} /></label>
                    <label>GRA <input type="number" min="0" max="9" step="0.5" value={peerGRA} onChange={(e) => setPeerGRA(e.target.value)} style={{ width: 70 }} /></label>
                  </div>
                  <textarea rows={2} value={peerStrengths} onChange={(e) => setPeerStrengths(e.target.value)} placeholder="优点（strengths）" style={{ width: '100%', marginBottom: 6 }} />
                  <textarea rows={2} value={peerImprovements} onChange={(e) => setPeerImprovements(e.target.value)} placeholder="改进建议（improvements）" style={{ width: '100%', marginBottom: 6 }} />
                  <textarea rows={3} value={peerComment} onChange={(e) => setPeerComment(e.target.value)} placeholder="综合评语（建议更具体）" style={{ width: '100%', marginBottom: 6 }} />
                  <button onClick={handlePeerReviewSubmit} disabled={peerReviewing}>
                    {peerReviewing ? '提交中...' : '提交互评'}
                  </button>
                </div>
              )}

              <div style={{ marginBottom: 8 }}>
                <h4>我的投稿</h4>
                <ul>
                  {peerMySubs.map((x) => (
                    <li key={x.id}>
                      {x.topic} | {x.status} | 评分数 {x.review_count} | 平均分 {Number(x.avg_overall_score || 0).toFixed(2)}
                    </li>
                  ))}
                  {peerMySubs.length === 0 && <li>暂无投稿</li>}
                </ul>
              </div>

              <div>
                <h4>我收到的互评</h4>
                <ul>
                  {peerReceived.map((x) => (
                    <li key={x.id}>
                      {x.topic || x.submission_id} | overall {Number(x.overall_score || 0).toFixed(2)} | 质量 {x.quality_tier}
                      <br />
                      优点：{x.strengths || '-'} | 建议：{x.improvements || '-'}
                    </li>
                  ))}
                  {peerReceived.length === 0 && <li>暂无收到互评</li>}
                </ul>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default Writing;
