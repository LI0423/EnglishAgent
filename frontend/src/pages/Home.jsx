import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts';
import {
  completeTodayLearningTask,
  getCurrentUser,
  getDashboardOverview,
  getGrowthInsights,
  getTodayLearningPlan,
} from '../utils/api';
import SidebarMenu from '../components/layout/SidebarMenu';
import TopNav from '../components/layout/TopNav';

const moduleRoutes = {
  listening: '/listening',
  reading: '/reading',
  writing: '/writing',
  speaking: '/speaking',
};

const moduleIcons = {
  listening: '🎧',
  reading: '📚',
  writing: '✍️',
  speaking: '💬',
};

const moduleColors = {
  listening: '#3B82F6',
  reading: '#10B981',
  writing: '#F59E0B',
  speaking: '#8B5CF6',
};

const statusLabels = {
  completed: '已完成',
  partial: '进行中',
  planned: '待完成',
  missed: '未完成',
  empty: '无计划',
};

const emptyCheckinCalendar = {
  month: '',
  streak_days: 0,
  completed_days: 0,
  planned_days: 0,
  today_status: 'empty',
  days: [],
};

const emptyDashboard = {
  summary: {
    username: '同学',
    learning_days: 0,
    streak_days: 0,
    total_completion: 0,
    current_band: null,
    target_band: 6.5,
  },
  vocabulary: {
    total: 0,
    weekly_new: 0,
    due_review: 0,
  },
  growth: {
    tracked_skills: 0,
    average_mastery: 0,
    due_review_count: 0,
    weak_skills: [],
    strong_skills: [],
  },
  modules: [],
  trend: [],
  checkin_calendar: emptyCheckinCalendar,
  recommendations: [],
  today_tasks: [],
};

const emptySmartPlan = {
  title: '今日智能学习安排',
  summary: '完成几次练习后，系统会给出更贴合你的安排。',
  tasks: [],
};

const emptyGrowthInsights = {
  abilities: [],
  due_memory_count: 0,
};

const Home = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState('同学');
  const [dashboard, setDashboard] = useState(emptyDashboard);
  const [smartPlan, setSmartPlan] = useState(emptySmartPlan);
  const [growthInsights, setGrowthInsights] = useState(emptyGrowthInsights);
  const [completingSmartTask, setCompletingSmartTask] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
      setLoading(true);
      setError('');
      try {
        const [user, overview, plan, insights] = await Promise.all([
          getCurrentUser().catch(() => null),
          getDashboardOverview(),
          getTodayLearningPlan(6).catch(() => emptySmartPlan),
          getGrowthInsights(8).catch(() => emptyGrowthInsights),
        ]);
        const nextUsername = user?.username || overview?.summary?.username || '同学';
        setUsername(nextUsername);
        setDashboard({
          ...emptyDashboard,
          ...overview,
          summary: {
            ...emptyDashboard.summary,
            ...(overview?.summary || {}),
            username: nextUsername,
          },
          vocabulary: {
            ...emptyDashboard.vocabulary,
            ...(overview?.vocabulary || {}),
          },
          growth: {
            ...emptyDashboard.growth,
            ...(overview?.growth || {}),
          },
          checkin_calendar: {
            ...emptyCheckinCalendar,
            ...(overview?.checkin_calendar || {}),
          },
        });
        setSmartPlan({
          ...emptySmartPlan,
          ...(plan || {}),
          tasks: Array.isArray(plan?.tasks) ? plan.tasks : [],
        });
        setGrowthInsights({
          ...emptyGrowthInsights,
          ...(insights || {}),
          abilities: Array.isArray(insights?.abilities) ? insights.abilities : [],
        });
      } catch (err) {
        setError(typeof err === 'string' ? err : '首页数据加载失败');
      } finally {
        setLoading(false);
      }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const summary = dashboard.summary || emptyDashboard.summary;
  const vocabulary = dashboard.vocabulary || emptyDashboard.vocabulary;
  const growth = dashboard.growth || emptyDashboard.growth;
  const checkinCalendar = dashboard.checkin_calendar || emptyCheckinCalendar;
  const totalCompletion = Math.max(0, Math.min(100, Number(summary.total_completion || 0)));
  const growthMastery = Math.round(Math.max(0, Math.min(1, Number(growth.average_mastery || 0))) * 100);
  const weakSkills = Array.isArray(growth.weak_skills) ? growth.weak_skills.slice(0, 4) : [];
  const smartTasks = Array.isArray(smartPlan.tasks) ? smartPlan.tasks.slice(0, 6) : [];
  const insightAbilities = Array.isArray(growthInsights.abilities)
    ? growthInsights.abilities.slice(0, 4)
    : [];
  const modules = (dashboard.modules || []).map((item) => ({
    ...item,
    icon: moduleIcons[item.module] || '•',
    color: moduleColors[item.module] || '#64748b',
    route: moduleRoutes[item.module] || '/',
  }));
  const trendData = useMemo(() => (
    (dashboard.trend || []).map((item) => ({
      ...item,
      minutes: Number(item.minutes || 0),
      sessions: Number(item.sessions || 0),
      done: Number(item.done || 0),
      total: Number(item.total || 0),
      completion_rate: Number(item.completion_rate || 0),
    }))
  ), [dashboard.trend]);
  const plannedTrendDays = trendData.filter((item) => item.total > 0);
  const weeklyCompletionAverage = plannedTrendDays.length
    ? Math.round(plannedTrendDays.reduce((sum, item) => sum + item.completion_rate, 0) / plannedTrendDays.length)
    : 0;
  const weeklyDoneTasks = trendData.reduce((sum, item) => sum + item.done, 0);
  const weeklyTotalTasks = trendData.reduce((sum, item) => sum + item.total, 0);
  const calendarDays = checkinCalendar.days || [];
  const leadingCalendarBlanks = calendarDays.length
    ? (new Date(`${calendarDays[0].date}T00:00:00`).getDay() + 6) % 7
    : 0;
  const todayStatusText = statusLabels[checkinCalendar.today_status] || '无计划';
  const goToRoute = (route) => {
    if (typeof route === 'string' && route.startsWith('/')) {
      navigate(route);
    }
  };
  const onCompleteSmartTask = async (taskId) => {
    const id = String(taskId || '').trim();
    if (!id) return;
    setCompletingSmartTask(id);
    setError('');
    try {
      await completeTodayLearningTask(id);
      await fetchData();
    } catch (err) {
      setError(typeof err === 'string' ? err : '智能任务完成失败');
    } finally {
      setCompletingSmartTask('');
    }
  };

  return (
    <div className="home-page web-dashboard">
      <TopNav username={username} />
      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>
        <div className="content-area">
          <main className="main-content">
            <section className="welcome-section">
              <div className="welcome-content">
                <h2>你好，{username}</h2>
                <p>加入学习第{summary.learning_days || 0}天，当前连续打卡{summary.streak_days || 0}天</p>
                <p>{summary.has_plan ? '保持当前进度，继续推进本周目标。' : '完成练习或创建学习计划后，首页会生成更完整的学习数据。'}</p>
              </div>
            </section>

            {error && <p className="ts-error">{error}</p>}
            {loading && <p className="ts-meta">正在读取真实学习数据...</p>}

            <section className="overview-cards">
              <div className="card">
                <h3>总完成度</h3>
                <div className="progress-circle-container">
                  <ResponsiveContainer width={120} height={120}>
                    <PieChart>
                      <Pie
                        data={[{ name: '完成', value: totalCompletion }, { name: '未完成', value: 100 - totalCompletion }]}
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
                  <div className="progress-text">{totalCompletion}%</div>
                </div>
              </div>
              <div className="card">
                <h3>词汇本</h3>
                <p className="big-number">{vocabulary.total || 0}</p>
                <p className="small-text">本周收录: {vocabulary.weekly_new || 0}</p>
              </div>
              <div className="card">
                <h3>连续学习</h3>
                <p className="big-number">{summary.streak_days || 0}天</p>
                <p className="small-text">{summary.streak_days > 0 ? '加油，保持势头！' : '今天完成一次练习即可点亮连续学习。'}</p>
              </div>
              <div className="card">
                <h3>总分预测</h3>
                <p className="big-number">{summary.current_band ? Number(summary.current_band).toFixed(1) : '暂无'}</p>
                <p className="small-text">目标: {summary.target_band || 6.5}</p>
              </div>
            </section>

            <section className="growth-overview-section">
              <div className="growth-overview-head">
                <div>
                  <h2>成长概览</h2>
                  <p>根据最近练习表现，动态整理当前掌握情况和下一步重点。</p>
                </div>
                <div className="growth-mastery-badge">{growthMastery}%</div>
              </div>
              <div className="growth-overview-grid">
                <div className="growth-metric">
                  <span>已追踪能力点</span>
                  <strong>{growth.tracked_skills || 0}</strong>
                </div>
                <div className="growth-metric">
                  <span>平均掌握度</span>
                  <strong>{growthMastery}%</strong>
                </div>
                <div className="growth-metric">
                  <span>建议复习</span>
                  <strong>{growth.due_review_count || 0}</strong>
                </div>
              </div>
              <div className="growth-focus-list">
                {weakSkills.length > 0 ? weakSkills.map((skill) => (
                  <div key={skill.skill_key} className="growth-focus-item">
                    <div>
                      <span>{formatSkillLabel(skill.skill_key)}</span>
                      <small>{formatSkillCategory(skill.category)} · 已练 {skill.exposure_count || 0} 次</small>
                    </div>
                    <strong>{Math.round(Number(skill.mastery || 0) * 100)}%</strong>
                  </div>
                )) : (
                  <div className="growth-focus-empty">完成几次练习后，这里会显示你的优先提升点。</div>
                )}
              </div>
            </section>

            <section className="smart-plan-section">
              <div className="smart-plan-head">
                <div>
                  <h2>{smartPlan.title || '今日智能学习安排'}</h2>
                  <p>{smartPlan.summary || emptySmartPlan.summary}</p>
                </div>
                <div className="smart-plan-count">{smartTasks.length || 0} 项</div>
              </div>
              <div className="smart-plan-grid">
                <div className="smart-task-list">
                  {smartTasks.length > 0 ? smartTasks.map((task, index) => (
                    <div
                      key={task.id || `${task.type || 'task'}-${task.title || index}`}
                      className={`smart-task-item ${task.completed ? 'completed' : ''}`}
                    >
                      <div className="smart-task-rank">{index + 1}</div>
                      <div className="smart-task-body">
                        <div className="smart-task-topline">
                          <span>{moduleLabel(task.module || '') || '学习'}</span>
                          <strong>{task.title}</strong>
                        </div>
                        <p>{task.reason || '根据最近练习情况安排。'}</p>
                      </div>
                      <div className="smart-task-actions">
                        {task.route && (
                          <button className="smart-task-action" onClick={() => goToRoute(task.route)}>
                            开始
                          </button>
                        )}
                        <button
                          className="smart-task-action"
                          disabled={Boolean(task.completed) || completingSmartTask === task.id}
                          onClick={() => onCompleteSmartTask(task.id)}
                        >
                          {task.completed ? '已完成' : (completingSmartTask === task.id ? '同步中...' : '完成')}
                        </button>
                      </div>
                    </div>
                  )) : (
                    <div className="smart-task-empty">完成一组练习后，这里会出现今日优先安排。</div>
                  )}
                </div>
                <div className="smart-insight-panel">
                  <div className="smart-insight-stat">
                    <span>待稳定内容</span>
                    <strong>{growthInsights.due_memory_count || 0}</strong>
                  </div>
                  <div className="smart-insight-list">
                    {insightAbilities.length > 0 ? insightAbilities.map((item) => (
                      <div key={item.ability_key} className={`smart-insight-item ${item.risk_level || 'normal'}`}>
                        <span>{formatAbilityLabel(item.ability_key)}</span>
                        <strong>{Math.round(Number(item.current_score || 0) * 100)}%</strong>
                      </div>
                    )) : (
                      <p>暂无明显波动，先按今日任务推进。</p>
                    )}
                  </div>
                </div>
              </div>
            </section>

            <section className="checkin-calendar-section">
              <div className="checkin-calendar-head">
                <div>
                  <h2>学习日历</h2>
                  <p>完成当天学习计划后即为打卡成功，连续学习天数按打卡成功天数统计。</p>
                </div>
                <div className="checkin-month">{checkinCalendar.month || '本月'}</div>
              </div>
              <div className="checkin-stats">
                <div className="checkin-stat">
                  <span>连续打卡</span>
                  <strong>{checkinCalendar.streak_days || 0}天</strong>
                </div>
                <div className="checkin-stat">
                  <span>本月完成</span>
                  <strong>{checkinCalendar.completed_days || 0}/{checkinCalendar.planned_days || 0}天</strong>
                </div>
                <div className="checkin-stat">
                  <span>今日状态</span>
                  <strong>{todayStatusText}</strong>
                </div>
              </div>
              <div className="checkin-grid" aria-label="学习打卡日历">
                {['一', '二', '三', '四', '五', '六', '日'].map((weekday) => (
                  <div key={weekday} className="checkin-weekday">{weekday}</div>
                ))}
                {Array.from({ length: leadingCalendarBlanks }).map((_, idx) => (
                  <div key={`blank-${idx}`} className="checkin-day checkin-day-blank" />
                ))}
                {calendarDays.map((day) => (
                  <div
                    key={day.date}
                    className={`checkin-day ${day.status || 'empty'} ${day.is_today ? 'today' : ''}`}
                    title={`${day.date} ${statusLabels[day.status] || '无计划'}`}
                  >
                    <span className="checkin-day-number">{day.day}</span>
                    {Number(day.total || 0) > 0 && (
                      <span className="checkin-day-progress">{day.done || 0}/{day.total || 0}</span>
                    )}
                  </div>
                ))}
              </div>
              <div className="checkin-legend">
                <span><i className="completed" />已完成</span>
                <span><i className="partial" />进行中</span>
                <span><i className="planned" />待完成</span>
                <span><i className="missed" />未完成</span>
                <span><i className="empty" />无计划</span>
              </div>
            </section>

            <section className="core-modules">
              <h2>核心功能</h2>
              <div className="modules-grid">
                {modules.map((module) => (
                  <div key={module.module} className="module-card">
                    <div className="module-icon" style={{ color: module.color }}>
                      {module.icon}
                    </div>
                    <h3>{module.name}</h3>
                    <p>今日已练习 {module.todayCount || 0}/{module.targetCount || 0}题</p>
                    <button className="module-button" onClick={() => goToRoute(module.route)}>开始练习</button>
                  </div>
                ))}
              </div>
            </section>

            <section className="learning-progress">
              <h2>学习进度</h2>
              <div className="progress-container">
                <div className="progress-summary-row">
                  <div>
                    <span>近 7 天计划完成率</span>
                    <strong>{weeklyCompletionAverage}%</strong>
                  </div>
                  <div>
                    <span>任务完成</span>
                    <strong>{weeklyDoneTasks}/{weeklyTotalTasks}</strong>
                  </div>
                </div>
                <div className="trend-chart">
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F8F9FA" />
                      <XAxis dataKey="day" stroke="#86909C" />
                      <YAxis stroke="#86909C" domain={[0, 100]} tickFormatter={(value) => `${value}%`} />
                      <Tooltip />
                      <Line type="monotone" dataKey="completion_rate" name="计划完成率" stroke="#0f766e" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="progress-day-list">
                  {trendData.map((item) => (
                    <div key={item.date} className="progress-day-item">
                      <span>{item.day}</span>
                      <strong>{item.done}/{item.total}</strong>
                      <small>{item.minutes}分钟</small>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="recommendations">
              <h2>个性化推荐</h2>
              <div className="recommendations-list">
                {(dashboard.recommendations || []).map((recommendation) => (
                  <div key={recommendation.id} className="recommendation-card">
                    <h3>{recommendation.title}</h3>
                    <p>{recommendation.description}</p>
                    <button
                      className="recommendation-button"
                      onClick={() => goToRoute(recommendation.route)}
                    >
                      去练习
                    </button>
                  </div>
                ))}
              </div>
            </section>

            <section className="tasks">
              <h2>今日任务</h2>
              <div className="tasks-list">
                {(dashboard.today_tasks || []).map((task) => (
                  <div key={task.id} className={`task-item ${task.completed ? 'completed' : ''}`}>
                    <input type="checkbox" checked={Boolean(task.completed)} readOnly />
                    <span className="task-title">{task.title}</span>
                    {task.route && (
                      <button className="task-action-btn" onClick={() => goToRoute(task.route)}>
                        开始
                      </button>
                    )}
                  </div>
                ))}
                {(dashboard.today_tasks || []).length === 0 && (
                  <div className="task-item">
                    <span className="task-title">暂无今日任务，创建学习计划后会自动同步。</span>
                  </div>
                )}
              </div>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
};

const formatSkillLabel = (skillKey = '') => {
  const text = String(skillKey || '');
  if (text.startsWith('module:')) {
    return moduleLabel(text.replace('module:', ''));
  }
  if (text.startsWith('topic:')) {
    return `话题：${text.replace('topic:', '')}`;
  }
  if (text.startsWith('word:')) {
    return `词汇：${text.replace('word:', '')}`;
  }
  const parts = text.split(':');
  if (parts.length >= 2) {
    return `${moduleLabel(parts[0])}：${parts.slice(1).join(' / ')}`;
  }
  return text || '能力点';
};

const moduleLabel = (key = '') => ({
  listening: '听力',
  reading: '阅读',
  writing: '写作',
  speaking: '口语',
  translation: '翻译',
  vocabulary: '词汇',
  mistakes: '错题',
})[key] || key;

const formatSkillCategory = (category = '') => ({
  module: '模块',
  skill: '能力',
  topic: '话题',
  mode: '练习形式',
  word: '词汇',
  difficulty: '难度',
})[category] || '能力';

const formatAbilityLabel = (key = '') => ({
  vocabulary: '词汇积累',
  mistake_review: '错题复盘',
  listening_detail: '听力细节',
  reading_accuracy: '阅读准确性',
  writing_task_response: '写作回应',
  writing_coherence: '写作连贯',
  writing_grammar: '写作语法',
  writing_lexical_resource: '写作词汇',
  speaking_coherence: '口语连贯',
  speaking_fluency: '口语流利度',
  speaking_grammar: '口语语法',
  speaking_vocabulary: '口语词汇',
  translation_accuracy: '翻译准确性',
  grammar: '语法能力',
  lexical: '词汇丰富度',
  pronunciation: '发音能力',
})[key] || String(key || '能力点').replaceAll('_', ' ');

export default Home;
