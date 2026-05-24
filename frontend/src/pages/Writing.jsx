import { useEffect, useState, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getCurrentUser } from '../utils/api';
import SidebarMenu from '../components/layout/SidebarMenu';
import {
  analyzeTask2Writing,
  analyzeTask1Writing,
  brainstormTask2,
  claimWritingPeerSubmission,
  getTask2CommonStructures,
  getMyWritingPeerSubmissions,
  getWritingPeerLeaderboard,
  getWritingPeerReviewAssist,
  getWritingPeerStats,
  getReceivedWritingPeerReviews,
  saveTask2Practice,
  saveTask1Practice,
  submitWritingPeerReview,
  submitWritingPeerSubmission,
} from '../utils/api';

import TopNav from "../components/layout/TopNav";
const Writing = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const [userData, setUserData] = useState({ username: '李同学' });
  const [writingContent, setWritingContent] = useState('');
  const [wordCount, setWordCount] = useState(0);
  const [timeRemaining, setTimeRemaining] = useState(40 * 60); // 40分钟
  const [taskType, setTaskType] = useState('task1');
  const [aiFeedback, setAiFeedback] = useState({});
  const [task2Brainstorm, setTask2Brainstorm] = useState(null);
  const [task2Structures, setTask2Structures] = useState([]);
  const [task2Stance, setTask2Stance] = useState('balanced');
  const [brainstorming, setBrainstorming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [replayNotice, setReplayNotice] = useState('');
  const [peerTopic, setPeerTopic] = useState('Task 1 图表描述练习');
  const [peerSubmitting, setPeerSubmitting] = useState(false);
  const [peerClaimed, setPeerClaimed] = useState(null);
  const [peerReviewing, setPeerReviewing] = useState(false);
  const [peerMySubs, setPeerMySubs] = useState([]);
  const [peerReceived, setPeerReceived] = useState([]);
  const [peerStats, setPeerStats] = useState(null);
  const [peerLeaderboard, setPeerLeaderboard] = useState([]);
  const [peerTR, setPeerTR] = useState(6);
  const [peerCC, setPeerCC] = useState(6);
  const [peerLR, setPeerLR] = useState(6);
  const [peerGRA, setPeerGRA] = useState(6);
  const [peerStrengths, setPeerStrengths] = useState('');
  const [peerImprovements, setPeerImprovements] = useState('');
  const [peerComment, setPeerComment] = useState('');
  const [peerAssistLoading, setPeerAssistLoading] = useState(false);
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

  useEffect(() => {
    setPeerTopic(taskType === 'task2' ? 'Task 2 观点论证练习' : 'Task 1 图表描述练习');
    setTimeRemaining(taskType === 'task2' ? 40 * 60 : 20 * 60);
    setAiFeedback({});
    if (taskType === 'task2') {
      getTask2CommonStructures()
        .then((res) => setTask2Structures(res?.structures || []))
        .catch(() => setTask2Structures([]));
    }
  }, [taskType]);

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
      const [subs, received, stats, board] = await Promise.all([
        getMyWritingPeerSubmissions(20),
        getReceivedWritingPeerReviews(null, 20),
        getWritingPeerStats(),
        getWritingPeerLeaderboard(8),
      ]);
      setPeerMySubs(subs || []);
      setPeerReceived(received || []);
      setPeerStats(stats || null);
      setPeerLeaderboard(board || []);
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
    } else if (qType === 'writing_task2') {
      setTaskType('task2');
    }
    setReplayNotice(questionId ? `来自错题重练：题目 ${questionId}` : '来自错题重练：建议先完成一篇写作练习');
  }, [location.search]);

  useEffect(() => {
    loadPeerData();
  }, []);

  // 模拟题目数据
  const task1Question = {
    title: '图表写作：2023年不同城市旅游人数',
    chartType: 'chart',
    requirements: '总结图表中的主要信息，比较数据并提供相关见解，至少150词。',
    exampleImage: '📊'
  };
  const task2Question = {
    title: '观点论证：大学教育是否应当免费',
    requirements: '围绕题目表达明确立场，给出论证与例子，至少250词。',
    prompt: 'Some people think higher education should be free for everyone. To what extent do you agree or disagree?',
  };
  const activeQuestion = taskType === 'task2' ? task2Question : task1Question;
  const targetWordCount = taskType === 'task2' ? 250 : 150;

  // 处理写作内容变化
  const handleContentChange = (e) => {
    setWritingContent(e.target.value);
  };

  // 保存草稿
  const handleSaveDraft = async () => {
    if (!writingContent.trim()) return;

    setSaving(true);
    try {
      if (taskType === 'task2') {
        await saveTask2Practice(
          writingContent,
          task2Question.title,
          [],
          task2Stance,
        );
      } else {
        await saveTask1Practice(
          writingContent,
          task1Question.chartType,
          task1Question.title,
        );
      }
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
      let analysis = null;
      if (taskType === 'task2') {
        analysis = await analyzeTask2Writing(
          writingContent,
          task2Question.title,
          [],
          task2Stance,
        );
      } else {
        analysis = await analyzeTask1Writing(
          writingContent,
          task1Question.chartType,
          task1Question.title,
        );
      }
      
      if (analysis) {
        setAiFeedback(analysis);
        alert('提交成功，已生成AI反馈！');
      }

      // 保存写作练习
      if (taskType === 'task2') {
        await saveTask2Practice(
          writingContent,
          task2Question.title,
          [],
          task2Stance,
        );
      } else {
        await saveTask1Practice(
          writingContent,
          task1Question.chartType,
          task1Question.title,
          analysis?.total_score,
        );
      }
    } catch (error) {
      console.error('Failed to submit writing:', error);
      alert('提交失败，请重试！');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTask2Brainstorm = async () => {
    setBrainstorming(true);
    try {
      const data = await brainstormTask2(task2Question.title, [], task2Stance);
      setTask2Brainstorm(data || null);
    } catch (error) {
      console.error('Failed to brainstorm task2:', error);
      alert(typeof error === 'string' ? error : '生成Task2思路失败，请重试');
    } finally {
      setBrainstorming(false);
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

  const handlePeerAssist = async () => {
    if (!peerClaimed?.id) return;
    setPeerAssistLoading(true);
    setPeerMessage('');
    try {
      const res = await getWritingPeerReviewAssist({ submission_id: peerClaimed.id });
      if (res) {
        setPeerTR(res.tr_score ?? 6);
        setPeerCC(res.cc_score ?? 6);
        setPeerLR(res.lr_score ?? 6);
        setPeerGRA(res.gra_score ?? 6);
        if (!peerStrengths.trim()) {
          setPeerStrengths((res.strengths || []).join('；'));
        }
        if (!peerImprovements.trim()) {
          setPeerImprovements((res.improvements || []).join('；'));
        }
        if (!peerComment.trim()) {
          setPeerComment(res.sample_comment || '');
        }
        setPeerMessage(`AI建议已生成（建议质量：${res.quality_hint || 'basic'}）`);
      }
    } catch (err) {
      setPeerMessage(typeof err === 'string' ? err : 'AI辅助生成失败');
    } finally {
      setPeerAssistLoading(false);
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
    <div className="home-page web-dashboard writing-page">
      {/* 顶部导航栏 */}
      <TopNav username={userData.username} />

      {/* 主要内容布局 */}
      <div className="main-layout">
        {/* 左侧导航栏 */}
        <div className="sidebar">
          <SidebarMenu />
        </div>

        {/* 右侧内容区 */}
        <div className="content-area content-shell">
          <main className="writing-content">
            {replayNotice && (
              <div className="card" style={{ marginBottom: 16, borderColor: '#7bb5ff', background: '#f3f8ff' }}>
                <h3>错题重练指引</h3>
                <p>{replayNotice}</p>
                <button onClick={() => navigate(`/mistakes?module=writing&questionType=${taskType === 'task2' ? 'writing_task2' : 'writing_task1'}`)}>返回错题本</button>
              </div>
            )}
            <div className="web-page-head">
              <div>
                <h2>写作练习</h2>
                <p>Task 1 / Task 2 写作训练、草稿保存、AI 反馈与互评。</p>
              </div>
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
                <h2 className="question-title">{activeQuestion.title}</h2>
                {taskType === 'task1' ? (
                  <div className="chart-placeholder">{task1Question.exampleImage}</div>
                ) : (
                  <div className="chart-placeholder">🧠</div>
                )}
                <div className="question-requirements">
                  <h3>写作要求：</h3>
                  <p>{activeQuestion.requirements}</p>
                  {taskType === 'task2' && (
                    <>
                      <p style={{ marginTop: 8 }}><strong>题干：</strong>{task2Question.prompt}</p>
                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                        立场
                        <select value={task2Stance} onChange={(e) => setTask2Stance(e.target.value)}>
                          <option value="agree">agree</option>
                          <option value="disagree">disagree</option>
                          <option value="balanced">balanced</option>
                        </select>
                        <button type="button" onClick={handleTask2Brainstorm} disabled={brainstorming}>
                          {brainstorming ? '生成中...' : '生成Task2思路'}
                        </button>
                      </label>
                    </>
                  )}
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
                        <h4>综合得分：<span className="score-value">{aiFeedback.total_score}/80</span></h4>
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

            {taskType === 'task2' && (task2Brainstorm || (task2Structures || []).length > 0) && (
              <div className="card" style={{ marginTop: 16 }}>
                <h3>Task 2 思路与结构建议</h3>
                {(task2Structures || []).length > 0 && (
                  <>
                    <h4>推荐结构</h4>
                    <ul>
                      {(task2Structures || []).map((x, idx) => (
                        <li key={idx}>{x}</li>
                      ))}
                    </ul>
                  </>
                )}
                {task2Brainstorm && (
                  <>
                    <h4>Thesis 备选</h4>
                    <ul>
                      {(task2Brainstorm.thesis_options || []).map((x, idx) => <li key={`thesis-${idx}`}>{x}</li>)}
                    </ul>
                    <h4>正方论点</h4>
                    <ul>
                      {(task2Brainstorm.arguments_for || []).map((x, idx) => <li key={`for-${idx}`}>{x}</li>)}
                    </ul>
                    <h4>反方论点</h4>
                    <ul>
                      {(task2Brainstorm.arguments_against || []).map((x, idx) => <li key={`against-${idx}`}>{x}</li>)}
                    </ul>
                    <h4>段落提纲</h4>
                    <ul>
                      {(task2Brainstorm.paragraph_outline || []).map((x, idx) => <li key={`outline-${idx}`}>{x}</li>)}
                    </ul>
                  </>
                )}
              </div>
            )}

            {/* 写作区域 */}
            <div className="writing-section">
              <div className="writing-header">
                <div className="writing-info">
                  <div className="timer">⏱️ {formatTime(timeRemaining)}</div>
                  <div className={`word-count ${wordCount >= targetWordCount ? 'target-reached' : ''}`}>
                    字数：{wordCount}/{targetWordCount}
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
                    disabled={submitting || !writingContent.trim() || wordCount < targetWordCount}
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

            <div className="card writing-peer-card">
              <div className="writing-peer-header">
                <h3>🤝 作文互评 2.0</h3>
                <div className="writing-peer-actions">
                  <input
                    className="peer-input"
                    value={peerTopic}
                    onChange={(e) => setPeerTopic(e.target.value)}
                    placeholder="互评题目标题"
                  />
                  <button onClick={handlePeerSubmit} disabled={peerSubmitting || !writingContent.trim() || writingContent.trim().length < 30}>
                    {peerSubmitting ? '投稿中...' : '投递当前作文'}
                  </button>
                  <button onClick={handlePeerClaim}>领取互评任务</button>
                </div>
                {peerMessage && <p className="peer-message">{peerMessage}</p>}
              </div>

              <div className="writing-peer-stats-grid">
                <div className="peer-stat-item">
                  <span>互评积分</span>
                  <strong>{peerStats?.total_points ?? 0}</strong>
                </div>
                <div className="peer-stat-item">
                  <span>互评等级</span>
                  <strong>{peerStats?.reviewer_level || 'review_newbie'}</strong>
                </div>
                <div className="peer-stat-item">
                  <span>已写互评</span>
                  <strong>{peerStats?.total_reviews_written ?? 0}</strong>
                </div>
                <div className="peer-stat-item">
                  <span>收到均分</span>
                  <strong>{Number(peerStats?.avg_received_score || 0).toFixed(2)}</strong>
                </div>
              </div>

              {peerStats?.reviewer_badges?.length > 0 && (
                <div className="peer-badges">
                  {peerStats.reviewer_badges.map((badge) => (
                    <span key={badge} className="peer-badge">{badge}</span>
                  ))}
                </div>
              )}

              {peerClaimed && (
                <div className="peer-review-panel">
                  <p><strong>待互评作文：</strong>{peerClaimed.topic}（{peerClaimed.task_type}）</p>
                  <p className="peer-claimed-content">{peerClaimed.content}</p>
                  <div className="peer-score-row">
                    <label>TR <input type="number" min="0" max="9" step="0.5" value={peerTR} onChange={(e) => setPeerTR(e.target.value)} /></label>
                    <label>CC <input type="number" min="0" max="9" step="0.5" value={peerCC} onChange={(e) => setPeerCC(e.target.value)} /></label>
                    <label>LR <input type="number" min="0" max="9" step="0.5" value={peerLR} onChange={(e) => setPeerLR(e.target.value)} /></label>
                    <label>GRA <input type="number" min="0" max="9" step="0.5" value={peerGRA} onChange={(e) => setPeerGRA(e.target.value)} /></label>
                  </div>
                  <textarea rows={2} value={peerStrengths} onChange={(e) => setPeerStrengths(e.target.value)} placeholder="优点（strengths）" />
                  <textarea rows={2} value={peerImprovements} onChange={(e) => setPeerImprovements(e.target.value)} placeholder="改进建议（improvements）" />
                  <textarea rows={3} value={peerComment} onChange={(e) => setPeerComment(e.target.value)} placeholder="综合评语（越具体质量越高）" />
                  <div className="peer-review-ops">
                    <button onClick={handlePeerAssist} disabled={peerAssistLoading}>
                      {peerAssistLoading ? '生成中...' : 'AI辅助生成评语'}
                    </button>
                    <button onClick={handlePeerReviewSubmit} disabled={peerReviewing}>
                      {peerReviewing ? '提交中...' : '提交互评'}
                    </button>
                  </div>
                </div>
              )}

              <div className="writing-peer-columns">
                <div>
                  <h4>我的投稿</h4>
                  <ul className="peer-list">
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
                  <ul className="peer-list">
                    {peerReceived.map((x) => (
                      <li key={x.id}>
                        {(x.topic || x.submission_id)} | overall {Number(x.overall_score || 0).toFixed(2)} | 质量 {x.quality_tier}
                        <br />
                        评阅者：{x.reviewer_alias || x.reviewer_id}
                        <br />
                        优点：{x.strengths || '-'} | 建议：{x.improvements || '-'}
                      </li>
                    ))}
                    {peerReceived.length === 0 && <li>暂无收到互评</li>}
                  </ul>
                </div>
              </div>

              <div>
                <h4>互评排行榜</h4>
                <ul className="peer-list">
                  {peerLeaderboard.map((x) => (
                    <li key={`${x.reviewer_id}-${x.rank}`}>
                      #{x.rank} {x.reviewer_alias} | 积分 {x.total_points} | 互评数 {x.total_reviews} | 高质量 {x.advanced_count}
                    </li>
                  ))}
                  {peerLeaderboard.length === 0 && <li>暂无排行榜数据</li>}
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
