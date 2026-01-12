import { useEffect, useState } from 'react';
import { CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getCurrentUser, getPlans, getPlanTasks, getProfile, getStatsOverview } from '../utils/api';

const Home = () => {
  const [userData, setUserData] = useState({
    username: '李同学',
    learningDays: 15,
    currentBand: 5.5,
    targetBand: 7.0,
    vocabulary: 3250,
    weeklyNewWords: 120,
    learningStreak: 7
  });



  // 获取用户数据
  useEffect(() => {
    const fetchUserData = async () => {
      try {
        // 获取当前用户信息
        const user = await getCurrentUser();
        if (user) {
          setUserData(prev => ({ ...prev, username: user.username }));
        }
        
        // 获取用户档案
        const profile = await getProfile();
        if (profile) {
          setUserData(prev => ({
            ...prev,
            currentBand: profile.current_band_overall,
            targetBand: profile.target_band,
            learningStreak: profile.learning_streak_days
          }));
        }
        
        // 获取统计概览
        const stats = await getStatsOverview();
        if (stats) {
          // 这里可以处理统计数据
        }
        
        // 获取学习计划
        const plans = await getPlans();
        if (plans && plans.length > 0) {
          // 获取第一个计划的任务
          const tasks = await getPlanTasks(plans[0].id);
          if (tasks) {
            // 这里可以处理任务数据
          }
        }
      } catch (err) {
        console.error('Failed to fetch user data:', err);
      }
    };

    fetchUserData();
  }, []);

  const [tasks, setTasks] = useState([
    { id: 1, title: '完成3篇听力练习', completed: false, target: 3, completedCount: 0 },
    { id: 2, title: '学习20个新词汇', completed: false, target: 20, completedCount: 0 },
    { id: 3, title: '复习上周错题', completed: false, target: 1, completedCount: 0 },
    { id: 4, title: '完成1篇写作练习', completed: false, target: 1, completedCount: 0 }
  ]);

  const [modules] = useState([
    { id: 1, name: '听力练习', icon: '🎧', todayCount: 0, targetCount: 3, color: '#3B82F6' },
    { id: 2, name: '阅读练习', icon: '📚', todayCount: 0, targetCount: 3, color: '#10B981' },
    { id: 3, name: '写作练习', icon: '✍️', todayCount: 0, targetCount: 2, color: '#F59E0B' },
    { id: 4, name: '口语练习', icon: '💬', todayCount: 0, targetCount: 2, color: '#8B5CF6' }
  ]);

  const [recommendations] = useState([
    { id: 1, title: '针对听力Section 3的专项练习', description: '提升讲座类听力理解能力' },
    { id: 2, title: '阅读匹配题技巧提升', description: '掌握快速定位关键词的方法' },
    { id: 3, title: '写作Task 2论证结构指导', description: '学习如何构建逻辑严密的论点' }
  ]);

  const [learningProgress] = useState({
    totalCompletion: 45,
    trendData: [
      { day: 'Mon', hours: 1.5 },
      { day: 'Tue', hours: 2.0 },
      { day: 'Wed', hours: 1.0 },
      { day: 'Thu', hours: 2.5 },
      { day: 'Fri', hours: 1.5 },
      { day: 'Sat', hours: 3.0 },
      { day: 'Sun', hours: 2.0 }
    ]
  });

  const handleTaskToggle = (taskId) => {
    setTasks(tasks.map(task => 
      task.id === taskId ? { ...task, completed: !task.completed } : task
    ));
  };



  return (
    <div className="home-page">
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
        {/* 左侧导航栏（网页端） */}
        <div className="sidebar">
          <div className="sidebar-header">
            <h2>🎓 IELTS Agent</h2>
          </div>
          <nav className="sidebar-nav">
            <ul>
              <li className="active">🏠 首页</li>
              <li>🎧 听力练习</li>
              <li>📚 阅读练习</li>
              <li>✍️ 写作练习</li>
              <li>💬 口语练习</li>
              <li>📝 词汇学习</li>
              <li>📊 学习报告</li>
              <li>🎯 个性化计划</li>
              <li>🏆 成就中心</li>
            </ul>
          </nav>
        </div>

        {/* 右侧内容区 */}
        <div className="content-area">

        <main className="main-content">
          {/* 欢迎区域 */}
          <section className="welcome-section">
            <div className="welcome-content">
              <h2>👋 你好，{userData.username}！</h2>
              <p>今天是你学习的第{userData.learningDays}天，已连续学习{userData.learningStreak}天</p>
              <p>🔥 保持当前进度，继续加油！</p>
            </div>
          </section>

          {/* 学习概览卡片 */}
          <section className="overview-cards">
            <div className="card">
              <h3>总完成度</h3>
              <div className="progress-circle-container">
                <ResponsiveContainer width={120} height={120}>
                  <PieChart>
                    <Pie
                      data={[{ name: '完成', value: learningProgress.totalCompletion }, { name: '未完成', value: 100 - learningProgress.totalCompletion }]}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={55}
                      paddingAngle={0}
                      dataKey="value"
                    >
                      <Cell key="0" fill="#4A6CF7" />
                      <Cell key="1" fill="#E9ECEF" />
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="progress-text">{learningProgress.totalCompletion}%</div>
              </div>
            </div>
            <div className="card">
              <h3>词汇量</h3>
              <p className="big-number">{userData.vocabulary}</p>
              <p className="small-text">本周新增: {userData.weeklyNewWords}</p>
            </div>
            <div className="card">
              <h3>连续学习</h3>
              <p className="big-number">{userData.learningStreak}天</p>
              <p className="small-text">加油，保持势头！</p>
            </div>
            <div className="card">
              <h3>总分预测</h3>
              <p className="big-number">{userData.currentBand}</p>
              <p className="small-text">目标: {userData.targetBand}</p>
            </div>
          </section>

          {/* 核心功能模块 */}
          <section className="core-modules">
            <h2>核心功能</h2>
            <div className="modules-grid">
              {modules.map(module => (
                <div key={module.id} className="module-card">
                  <div className="module-icon" style={{ color: module.color }}>
                    {module.icon}
                  </div>
                  <h3>{module.name}</h3>
                  <p>今日已练习 {module.todayCount}/{module.targetCount}题</p>
                  <button className="module-button">开始练习</button>
                </div>
              ))}
            </div>
          </section>

          {/* 学习进度图表 */}
          <section className="learning-progress">
            <h2>学习进度</h2>
            <div className="progress-container">
              <div className="trend-chart">
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={learningProgress.trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F8F9FA" />
                    <XAxis dataKey="day" stroke="#86909C" />
                    <YAxis stroke="#86909C" />
                    <Tooltip />
                    <Line type="monotone" dataKey="hours" stroke="#4A6CF7" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          {/* 个性化推荐 */}
          <section className="recommendations">
            <h2>个性化推荐</h2>
            <div className="recommendations-list">
              {recommendations.map(recommendation => (
                <div key={recommendation.id} className="recommendation-card">
                  <h3>{recommendation.title}</h3>
                  <p>{recommendation.description}</p>
                  <button className="recommendation-button">查看详情</button>
                </div>
              ))}
            </div>
          </section>

          {/* 今日任务 */}
          <section className="tasks">
            <h2>今日任务</h2>
            <div className="tasks-list">
              {tasks.map(task => (
                <div key={task.id} className={`task-item ${task.completed ? 'completed' : ''}`}>
                  <input 
                    type="checkbox" 
                    checked={task.completed} 
                    onChange={() => handleTaskToggle(task.id)}
                  />
                  <span className="task-title">{task.title}</span>
                </div>
              ))}
            </div>
          </section>
        </main>
      </div>
    </div>
  </div>
  );
};

export default Home;