import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  applyPlanExecutionReminders,
  applyPlanIntervention,
  createLearningPlan,
  generatePlan7d,
  generateWeeklyPlanTasks,
  getPlanReminderSuggestions,
  getPlanCalibrationLogs,
  getPlanHealthReport,
  getPlanInterventionPreview,
  getPlanInterventionStatus,
  getReminderPreferences,
  getLearningPlanProgress,
  getLearningPlanTasks,
  getMistakeModuleComparison,
  getMistakeWeeklyFocus,
  getPlans,
  updateLearningPlanSettings,
  updateReminderPreferences,
  updatePlanTaskProgress,
} from '../utils/api';
import SidebarMenu from '../components/layout/SidebarMenu';

import TopNav from "../components/layout/TopNav";
function Plans() {
  const navigate = useNavigate();

  const [plans, setPlans] = useState([]);
  const [plan7d, setPlan7d] = useState(null);
  const [weeklyFocus, setWeeklyFocus] = useState(null);
  const [focusDays, setFocusDays] = useState(14);
  const [focusMinutes, setFocusMinutes] = useState(90);
  const [taskDays, setTaskDays] = useState(7);
  const [creatingTasksPlanId, setCreatingTasksPlanId] = useState('');
  const [taskGenMessage, setTaskGenMessage] = useState('');
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [planTasks, setPlanTasks] = useState([]);
  const [planProgress, setPlanProgress] = useState(null);
  const [moduleRiskRows, setModuleRiskRows] = useState([]);
  const [updatingTaskKey, setUpdatingTaskKey] = useState('');
  const [calibrating, setCalibrating] = useState(false);
  const [moduleFilter, setModuleFilter] = useState('all');
  const [showPendingOnly, setShowPendingOnly] = useState(false);
  const [recentlyDoneTaskKey, setRecentlyDoneTaskKey] = useState('');
  const [loopWindowDays, setLoopWindowDays] = useState(14);
  const [planHealth, setPlanHealth] = useState(null);
  const [calibrationLogs, setCalibrationLogs] = useState([]);
  const [interventionStatus, setInterventionStatus] = useState(null);
  const [interventionDays, setInterventionDays] = useState(14);
  const [interventionRemedialDays, setInterventionRemedialDays] = useState(3);
  const [interventionPreview, setInterventionPreview] = useState(null);
  const [loadingLoop, setLoadingLoop] = useState(false);
  const [previewingIntervention, setPreviewingIntervention] = useState(false);
  const [applyingIntervention, setApplyingIntervention] = useState(false);
  const [applyingPreviewPlan, setApplyingPreviewPlan] = useState(false);
  const [planReminderSuggestions, setPlanReminderSuggestions] = useState(null);
  const [loadingPlanReminders, setLoadingPlanReminders] = useState(false);
  const [creatingPlanReminders, setCreatingPlanReminders] = useState(false);
  const [loadingReminderPrefs, setLoadingReminderPrefs] = useState(false);
  const [savingReminderPrefs, setSavingReminderPrefs] = useState(false);
  const [reminderPrefs, setReminderPrefs] = useState({
    enabled: true,
    channels: ['app'],
    preferred_times: [],
    quiet_hours: null,
    strategy_config: {
      frequency_window_hours: 3,
      max_reminders_per_window: 2,
      preferred_tolerance_minutes: 90,
      merge_similar_enabled: true,
      high_priority_bypass_cap: true,
    },
  });
  const [error, setError] = useState('');

  const loadPlans = async () => {
    try {
      const data = await getPlans();
      setPlans(data);
      if (data.length > 0 && !selectedPlanId) {
        setSelectedPlanId(data[0].id);
      }
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载计划失败');
    }
  };

  const loadWeeklyFocus = async (days = focusDays, minutes = focusMinutes) => {
    try {
      const data = await getMistakeWeeklyFocus(days, minutes);
      setWeeklyFocus(data);
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载智能计划建议失败');
      setWeeklyFocus(null);
    }
  };

  const loadModuleRisk = async (days = focusDays) => {
    try {
      const rows = await getMistakeModuleComparison(days);
      setModuleRiskRows(Array.isArray(rows) ? rows : []);
    } catch {
      setModuleRiskRows([]);
    }
  };

  const loadReminderPrefs = async () => {
    setLoadingReminderPrefs(true);
    setError('');
    try {
      const data = await getReminderPreferences();
      const strategy = data?.strategy_config || {};
      setReminderPrefs({
        enabled: typeof data?.enabled === 'boolean' ? data.enabled : true,
        channels: Array.isArray(data?.channels) && data.channels.length > 0 ? data.channels : ['app'],
        preferred_times: Array.isArray(data?.preferred_times) ? data.preferred_times : [],
        quiet_hours: data?.quiet_hours || null,
        strategy_config: {
          frequency_window_hours: Number(strategy.frequency_window_hours ?? 3),
          max_reminders_per_window: Number(strategy.max_reminders_per_window ?? 2),
          preferred_tolerance_minutes: Number(strategy.preferred_tolerance_minutes ?? 90),
          merge_similar_enabled: typeof strategy.merge_similar_enabled === 'boolean' ? strategy.merge_similar_enabled : true,
          high_priority_bypass_cap: typeof strategy.high_priority_bypass_cap === 'boolean' ? strategy.high_priority_bypass_cap : true,
        },
      });
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载提醒偏好失败');
    } finally {
      setLoadingReminderPrefs(false);
    }
  };

  useEffect(() => {
    loadPlans();
    loadWeeklyFocus();
    loadModuleRisk();
    loadReminderPrefs();
  }, []);

  const loadSelectedPlanTasks = async (planId) => {
    if (!planId) {
      setPlanTasks([]);
      setPlanProgress(null);
      return;
    }
    try {
      const [tasks, progress] = await Promise.all([
        getLearningPlanTasks(planId),
        getLearningPlanProgress(planId),
      ]);
      setPlanTasks(tasks || []);
      setPlanProgress(progress || null);
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载计划任务失败');
      setPlanTasks([]);
      setPlanProgress(null);
    }
  };

  const loadPlanClosedLoop = async (planId, days = loopWindowDays) => {
    if (!planId) {
      setPlanHealth(null);
      setCalibrationLogs([]);
      setInterventionStatus(null);
      return;
    }
    setLoadingLoop(true);
    try {
      const [health, logs, status] = await Promise.all([
        getPlanHealthReport(planId, days),
        getPlanCalibrationLogs(planId, 20),
        getPlanInterventionStatus(planId, days),
      ]);
      setPlanHealth(health || null);
      setCalibrationLogs(Array.isArray(logs) ? logs : []);
      setInterventionStatus(status || null);
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载计划闭环数据失败');
      setPlanHealth(null);
      setCalibrationLogs([]);
      setInterventionStatus(null);
    } finally {
      setLoadingLoop(false);
    }
  };

  useEffect(() => {
    loadSelectedPlanTasks(selectedPlanId);
    loadPlanClosedLoop(selectedPlanId, loopWindowDays);
    setPlanReminderSuggestions(null);
  }, [selectedPlanId]);

  useEffect(() => {
    if (selectedPlanId) {
      loadPlanClosedLoop(selectedPlanId, loopWindowDays);
    }
  }, [loopWindowDays]);

  const formatDate = (ts) => {
    const value = Number(ts || 0) * 1000;
    if (!value) return '-';
    const d = new Date(value);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  const formatDateTime = (ts) => {
    const value = Number(ts || 0) * 1000;
    if (!value) return '-';
    const d = new Date(value);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${day} ${hh}:${mm}`;
  };

  const normalizeModule = (raw) => {
    const v = String(raw || '').toLowerCase().trim();
    if (!v) return '';
    if (v.includes('listen')) return 'listening';
    if (v.includes('read')) return 'reading';
    if (v.includes('writ')) return 'writing';
    if (v.includes('speak')) return 'speaking';
    if (v.includes('vocab')) return 'vocabulary';
    return v;
  };

  const moduleLabel = (module) => {
    const mapping = {
      listening: '听力',
      reading: '阅读',
      writing: '写作',
      speaking: '口语',
      vocabulary: '词汇',
    };
    return mapping[module] || module || '未分类';
  };

  const routeByModule = (module) => {
    const v = normalizeModule(module);
    if (v === 'listening') return '/listening';
    if (v === 'reading') return '/reading';
    if (v === 'writing') return '/writing';
    if (v === 'speaking') return '/speaking';
    if (v === 'vocabulary') return '/vocabulary';
    return '/mistakes';
  };

  const goModulePractice = (module) => {
    const v = normalizeModule(module);
    if (!v) return;
    const params = new URLSearchParams({
      from: 'plans',
      module: v,
      source: 'plan_execution',
    });
    navigate(`${routeByModule(v)}?${params.toString()}`);
  };

  const goModuleMistakes = (module) => {
    const v = normalizeModule(module);
    if (!v) return;
    const params = new URLSearchParams({
      module: v,
      queueSort: 'priority',
      from: 'plans',
    });
    navigate(`/mistakes?${params.toString()}`);
  };

  const inferTaskModule = (task) => {
    const explicit = normalizeModule(task?.module);
    if (explicit) return explicit;
    const text = `${task?.title || ''} ${task?.description || ''}`;
    return normalizeModule(text);
  };

  const todayDateText = formatDate(Math.floor(Date.now() / 1000));

  const refreshSelectedPlanPanels = async (planId = selectedPlanId) => {
    await Promise.all([
      loadSelectedPlanTasks(planId),
      loadPlanClosedLoop(planId, loopWindowDays),
    ]);
  };

  const loadPlanReminderSuggestions = async (planId = selectedPlanId) => {
    if (!planId) return;
    setLoadingPlanReminders(true);
    setError('');
    try {
      const data = await getPlanReminderSuggestions(planId, interventionDays, 'app');
      setPlanReminderSuggestions(data || null);
    } catch (e) {
      setError(typeof e === 'string' ? e : '获取计划提醒建议失败');
      setPlanReminderSuggestions(null);
    } finally {
      setLoadingPlanReminders(false);
    }
  };

  const moduleOptions = useMemo(() => {
    const set = new Set();
    planTasks.forEach((d) => {
      (d.tasks || []).forEach((t) => {
        const module = normalizeModule(t.module);
        if (module) set.add(module);
      });
    });
    return Array.from(set);
  }, [planTasks]);

  const selectedPlan = useMemo(
    () => plans.find((p) => p.id === selectedPlanId) || null,
    [plans, selectedPlanId],
  );

  const visibleDailyTasks = useMemo(() => {
    const sorted = [...(planTasks || [])].sort((a, b) => Number(a.date || 0) - Number(b.date || 0));
    const withTodayFirst = sorted.sort((a, b) => {
      const ad = formatDate(a.date);
      const bd = formatDate(b.date);
      if (ad === todayDateText && bd !== todayDateText) return -1;
      if (bd === todayDateText && ad !== todayDateText) return 1;
      return Number(a.date || 0) - Number(b.date || 0);
    });
    return withTodayFirst
      .map((daily) => {
        let filteredTasks = (daily.tasks || []).filter((t) => {
          if (moduleFilter === 'all') return true;
          return normalizeModule(t.module) === moduleFilter;
        });
        if (showPendingOnly) {
          filteredTasks = filteredTasks.filter((t) => !t.completed);
        }
        return { ...daily, tasks: filteredTasks };
      })
      .filter((daily) => daily.tasks.length > 0);
  }, [planTasks, moduleFilter, showPendingOnly]);

  const weeklyTrend = useMemo(() => {
    const dayMap = {};
    (planTasks || []).forEach((daily) => {
      const dayText = formatDate(daily.date);
      const tasks = daily.tasks || [];
      const total = tasks.length;
      const done = tasks.filter((t) => Boolean(t.completed)).length;
      dayMap[dayText] = { done, total };
    });
    const arr = [];
    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - i);
      const dayText = formatDate(Math.floor(d.getTime() / 1000));
      const daily = dayMap[dayText] || { done: 0, total: 0 };
      const percent = daily.total > 0 ? (daily.done / daily.total) * 100 : 0;
      arr.push({
        dayText,
        label: dayText.slice(5),
        done: daily.done,
        total: daily.total,
        percent,
        isToday: dayText === todayDateText,
      });
    }
    return arr;
  }, [planTasks]);

  const moduleCompletionStats = useMemo(() => {
    const map = {};
    (planTasks || []).forEach((daily) => {
      (daily.tasks || []).forEach((task) => {
        const module = inferTaskModule(task) || 'unknown';
        if (!map[module]) {
          map[module] = { module, done: 0, total: 0 };
        }
        map[module].total += 1;
        if (task.completed) {
          map[module].done += 1;
        }
      });
    });
    return Object.values(map)
      .map((item) => ({
        ...item,
        rate: item.total > 0 ? (item.done / item.total) * 100 : 0,
      }))
      .sort((a, b) => b.total - a.total);
  }, [planTasks]);

  const executionReminder = useMemo(() => {
    const todayPending = [];
    const overduePending = [];
    const allPending = [];
    (planTasks || []).forEach((daily) => {
      const dayText = formatDate(daily.date);
      (daily.tasks || []).forEach((task) => {
        if (task.completed) return;
        const item = {
          dailyId: daily.id,
          dayText,
          title: task.title,
          module: inferTaskModule(task) || 'unknown',
          timeRequired: Number(task.time_required || 0),
        };
        allPending.push(item);
        if (dayText === todayDateText) {
          todayPending.push(item);
        } else if (dayText < todayDateText) {
          overduePending.push(item);
        }
      });
    });
    const candidates = [...overduePending, ...todayPending, ...allPending]
      .sort((a, b) => {
        const rank = (x) => (x.dayText < todayDateText ? 2 : x.dayText === todayDateText ? 1 : 0);
        const diff = rank(b) - rank(a);
        if (diff !== 0) return diff;
        return (b.timeRequired || 0) - (a.timeRequired || 0);
      });
    const dedup = [];
    const seen = new Set();
    candidates.forEach((x) => {
      const key = `${x.dailyId}:${x.title}`;
      if (!seen.has(key)) {
        seen.add(key);
        dedup.push(x);
      }
    });
    return {
      todayPendingCount: todayPending.length,
      overduePendingCount: overduePending.length,
      allPendingCount: allPending.length,
      remainingMinutes: allPending.reduce((sum, x) => sum + (x.timeRequired || 0), 0),
      topSuggestions: dedup.slice(0, 3),
    };
  }, [planTasks, todayDateText]);

  const paceCalibration = useMemo(() => {
    if (!selectedPlan) return null;
    const rows = [];
    for (let i = 2; i >= 0; i -= 1) {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - i);
      const dayText = formatDate(Math.floor(d.getTime() / 1000));
      const daily = (planTasks || []).find((x) => formatDate(x.date) === dayText);
      if (!daily) continue;
      const total = (daily.tasks || []).length;
      const done = (daily.tasks || []).filter((t) => Boolean(t.completed)).length;
      if (total <= 0) continue;
      rows.push({ dayText, done, total, rate: (done / total) * 100 });
    }
    const hasEnough = rows.length >= 2;
    const avgRate = rows.length > 0
      ? rows.reduce((sum, x) => sum + x.rate, 0) / rows.length
      : 0;
    const currentMinutes = Number(selectedPlan.daily_minutes || 90);
    let nextMinutes = currentMinutes;
    let action = 'keep';
    let reason = '近3天执行稳定，建议保持当前节奏。';
    if (hasEnough && avgRate < 50) {
      nextMinutes = Math.max(30, Math.round(currentMinutes * 0.85));
      action = 'decrease';
      reason = '近3天执行率偏低，建议先降低每日时长，提升可持续性。';
    } else if (hasEnough && avgRate >= 85) {
      nextMinutes = Math.min(240, Math.round(currentMinutes * 1.1));
      action = 'increase';
      reason = '近3天执行率较高，可适度加量提升进步速度。';
    }
    const riskModules = (moduleRiskRows || [])
      .map((x) => normalizeModule(x.module))
      .filter(Boolean)
      .slice(0, 3);
    const nextFocusModules = riskModules.length > 0
      ? riskModules
      : (selectedPlan.focus_modules || []);
    return {
      hasEnough,
      avgRate,
      currentMinutes,
      nextMinutes,
      action,
      reason,
      rows,
      nextFocusModules,
    };
  }, [selectedPlan, planTasks, moduleRiskRows]);

  return (
    <div className="home-page web-dashboard plan-page">
      <TopNav />
      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>
        <div className="content-area content-shell">
          <div className="web-page-head">
            <div>
              <h2>个性化计划</h2>
              <p>策略生成、任务执行与干预闭环统一在计划工作台。</p>
            </div>
            <div className="web-page-head-actions">
              <button onClick={loadPlans}>刷新计划</button>
            </div>
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>智能周计划建议（基于错题风险）</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button onClick={() => { setFocusDays(7); loadWeeklyFocus(7, focusMinutes); loadModuleRisk(7); }} disabled={focusDays === 7}>近7天</button>
              <button onClick={() => { setFocusDays(14); loadWeeklyFocus(14, focusMinutes); loadModuleRisk(14); }} disabled={focusDays === 14}>近14天</button>
              <button onClick={() => { setFocusDays(30); loadWeeklyFocus(30, focusMinutes); loadModuleRisk(30); }} disabled={focusDays === 30}>近30天</button>
              <label style={{ marginLeft: 8 }}>每日分钟：</label>
              <input
                type="number"
                min="30"
                max="240"
                value={focusMinutes}
                onChange={(e) => setFocusMinutes(Number(e.target.value) || 90)}
                style={{ width: 100 }}
              />
              <button onClick={() => { loadWeeklyFocus(focusDays, focusMinutes); loadModuleRisk(focusDays); }}>刷新建议</button>
            </div>
            {weeklyFocus ? (
              <div>
                <p>{weeklyFocus.summary}</p>
                <p>主攻模块：<strong>{weeklyFocus.focus_module || '—'}</strong></p>
                <ul>
                  {(weeklyFocus.module_allocations || []).map((x) => (
                    <li key={`${x.module}_${x.percent}`}>
                      {x.module}：{x.percent}%（约 {x.minutes} 分钟/天） · {x.reason}{' '}
                      <button type="button" className="plan-link-btn" onClick={() => goModuleMistakes(x.module)}>查看错题</button>
                      <button type="button" className="plan-link-btn" onClick={() => goModulePractice(x.module)}>去练习</button>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={async () => {
                    setError('');
                    setTaskGenMessage('');
                    try {
                      const modules = (weeklyFocus.module_allocations || []).map((x) => String(x.module || '')).filter(Boolean);
                      const created = await createLearningPlan({
                        target_band: 7.0,
                        daily_minutes: Number(weeklyFocus.total_daily_minutes || focusMinutes || 90),
                        focus_modules: modules.length > 0 ? modules : ['listening', 'reading', 'writing', 'speaking'],
                        duration_weeks: 8,
                      });
                      if (created?.plan_id) {
                        const generated = await generateWeeklyPlanTasks(created.plan_id, taskDays);
                        setTaskGenMessage(generated?.message || '已自动生成每日任务');
                      }
                      await loadPlans();
                      await refreshSelectedPlanPanels(created?.plan_id || selectedPlanId);
                    } catch (e) {
                      setError(typeof e === 'string' ? e : '按建议创建计划失败');
                    }
                  }}
                >
                  按建议创建长期计划并生成任务
                </button>
              </div>
            ) : (
              <p>暂无智能建议数据。</p>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>快速生成 7 天计划</h3>
            <button
              onClick={async () => {
                setError('');
                try {
                  const data = await generatePlan7d(['limited vocabulary', 'grammar errors'], 7.0, '1-2 hours');
                  setPlan7d(data);
                } catch (e) {
                  setError(typeof e === 'string' ? e : '生成失败');
                }
              }}
            >
              生成7天计划
            </button>
            {plan7d && (
              <div style={{ marginTop: 12 }}>
                <p>{plan7d.summary}</p>
                <p>total_hours: {plan7d.total_hours}</p>
                <ul>
                  {(plan7d.plan || []).map((day) => (
                    <li key={day.day}>{day.day} - {day.focus_area}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>创建长期学习计划</h3>
            <button
              onClick={async () => {
                setError('');
                try {
                  await createLearningPlan({
                    target_band: 7.0,
                    daily_minutes: 90,
                    focus_modules: ['listening', 'reading', 'writing', 'speaking'],
                    duration_weeks: 8,
                  });
                  await loadPlans();
                  await refreshSelectedPlanPanels(selectedPlanId);
                } catch (e) {
                  setError(typeof e === 'string' ? e : '创建失败');
                }
              }}
            >
              创建计划（示例）
            </button>
          </div>

          <div className="card">
            <h3>我的计划列表</h3>
            <button onClick={loadPlans}>刷新</button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '10px 0' }}>
              <label>任务生成天数：</label>
              <input
                type="number"
                min="1"
                max="28"
                value={taskDays}
                onChange={(e) => setTaskDays(Math.max(1, Math.min(28, Number(e.target.value) || 7)))}
                style={{ width: 90 }}
              />
            </div>
            <ul>
              {plans.map((p) => (
                <li key={p.id}>
                  {p.id} | target_band: {p.target_band} | daily_minutes: {p.daily_minutes} | status: {p.status}
                  {' '}
                  <button
                    onClick={async () => {
                      setError('');
                      setTaskGenMessage('');
                      setCreatingTasksPlanId(p.id);
                      try {
                        const generated = await generateWeeklyPlanTasks(p.id, taskDays);
                        setTaskGenMessage(`计划 ${p.id.slice(0, 8)}：${generated?.message || '已生成任务'}`);
                        if (p.id === selectedPlanId) {
                          await refreshSelectedPlanPanels(p.id);
                        }
                      } catch (e) {
                        setError(typeof e === 'string' ? e : '生成每日任务失败');
                      } finally {
                        setCreatingTasksPlanId('');
                      }
                    }}
                    disabled={creatingTasksPlanId === p.id}
                    style={{ marginLeft: 8 }}
                  >
                    {creatingTasksPlanId === p.id ? '生成中...' : '生成每日任务'}
                  </button>
                </li>
              ))}
              {plans.length === 0 && <li>暂无计划</li>}
            </ul>
            {taskGenMessage && <p style={{ color: '#0b8f83' }}>{taskGenMessage}</p>}
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3>计划任务执行面板</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <label>选择计划：</label>
              <select
                value={selectedPlanId}
                onChange={(e) => setSelectedPlanId(e.target.value)}
                style={{ minWidth: 280 }}
              >
                {plans.length === 0 && <option value="">暂无计划</option>}
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id.slice(0, 8)} | {p.status} | {p.daily_minutes} 分钟/天
                  </option>
                ))}
              </select>
              <button onClick={() => refreshSelectedPlanPanels(selectedPlanId)} disabled={!selectedPlanId}>
                刷新任务
              </button>
              <label style={{ marginLeft: 6 }}>模块筛选：</label>
              <select
                value={moduleFilter}
                onChange={(e) => setModuleFilter(e.target.value)}
                className="plan-input"
              >
                <option value="all">全部模块</option>
                {moduleOptions.map((m) => (
                  <option key={m} value={m}>{moduleLabel(m)}</option>
                ))}
              </select>
            </div>

            {planProgress && (
              <div className="plan-progress-wrap">
                <p style={{ marginBottom: 8 }}>
                总体进度：{planProgress.completed_tasks}/{planProgress.total_tasks} 天，
                完成率 {Number(planProgress.completion_rate || 0).toFixed(1)}%
                </p>
                <div className="plan-progress-bar">
                  <span style={{ width: `${Math.max(0, Math.min(100, Number(planProgress.completion_rate || 0)))}%` }} />
                </div>
              </div>
            )}

            <div className="plan-reminder-panel plan-loop-panel">
              <div className="plan-reminder-head">
                <h4>执行健康与干预闭环</h4>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label>观察窗口：</label>
                  <select
                    value={loopWindowDays}
                    onChange={(e) => setLoopWindowDays(Number(e.target.value) || 14)}
                    className="plan-input"
                  >
                    <option value={7}>近7天</option>
                    <option value={14}>近14天</option>
                    <option value={30}>近30天</option>
                  </select>
                  <button
                    className="plan-filter-btn"
                    onClick={() => loadPlanClosedLoop(selectedPlanId, loopWindowDays)}
                    disabled={!selectedPlanId || loadingLoop}
                  >
                    {loadingLoop ? '刷新中...' : '刷新'}
                  </button>
                </div>
              </div>

              {planHealth ? (
                <>
                  <div className="plan-reminder-metrics">
                    <span>
                      健康等级：
                      <strong className={`plan-health-badge ${planHealth.health_level || 'unknown'}`}>
                        {planHealth.health_level || 'unknown'}
                      </strong>
                    </span>
                    <span>任务完成率：{Number(planHealth.task_completion_rate || 0).toFixed(1)}%</span>
                    <span>天完成率：{Number(planHealth.day_completion_rate || 0).toFixed(1)}%</span>
                    <span>连续完成：{Number(planHealth.streak_days || 0)} 天</span>
                  </div>
                  {Array.isArray(planHealth.module_stats) && planHealth.module_stats.length > 0 && (
                    <div className="plan-suggest-list">
                      {planHealth.module_stats.slice(0, 4).map((row) => (
                        <div key={`${row.module}_${row.total || 0}`} className="plan-suggest-item">
                          <span>{moduleLabel(normalizeModule(row.module))}</span>
                          <span>完成 {Number(row.done || 0)}/{Number(row.total || 0)} · {Number(row.completion_rate || 0).toFixed(0)}%</span>
                          <span className="plan-suggest-actions">
                            <button type="button" className="plan-link-btn" onClick={() => goModulePractice(row.module)}>去练习</button>
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="plan-loop-grid">
                    <div className="plan-loop-card">
                      <h5>校准日志（最近5条）</h5>
                      {(calibrationLogs || []).slice(0, 5).map((log) => (
                        <div key={log.id} className="plan-loop-log-item">
                          <div>
                            {log.source || 'manual'} · {formatDateTime(log.created_at)}
                          </div>
                          <div>
                            {Number(log.before_daily_minutes || 0)} → {Number(log.after_daily_minutes || 0)} 分钟
                          </div>
                          {log.note && <div className="plan-loop-subtle">{log.note}</div>}
                        </div>
                      ))}
                      {(!calibrationLogs || calibrationLogs.length === 0) && <p className="plan-loop-subtle">暂无校准记录</p>}
                    </div>

                    <div className="plan-loop-card">
                      <h5>干预状态</h5>
                      {interventionStatus ? (
                        <>
                          <p>
                            干预任务完成：{interventionStatus.intervention_done}/{interventionStatus.intervention_total}
                            {' '}（{Number(interventionStatus.intervention_completion_rate || 0).toFixed(1)}%）
                          </p>
                          <p>干预批次：{interventionStatus.batch_count || 0}</p>
                          <p>最近批次：{interventionStatus.latest_batch_id ? interventionStatus.latest_batch_id.slice(0, 8) : '无'}</p>
                        </>
                      ) : (
                        <p className="plan-loop-subtle">暂无干预统计</p>
                      )}
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                        <label>评估天数：</label>
                        <input
                          type="number"
                          min="3"
                          max="30"
                          value={interventionDays}
                          onChange={(e) => setInterventionDays(Math.max(3, Math.min(30, Number(e.target.value) || 14)))}
                          className="plan-input"
                          style={{ width: 90 }}
                        />
                        <label>干预天数：</label>
                        <input
                          type="number"
                          min="1"
                          max="7"
                          value={interventionRemedialDays}
                          onChange={(e) => setInterventionRemedialDays(Math.max(1, Math.min(7, Number(e.target.value) || 3)))}
                          className="plan-input"
                          style={{ width: 90 }}
                        />
                        <button
                          className="plan-filter-btn"
                          disabled={!selectedPlanId || previewingIntervention}
                          onClick={async () => {
                            if (!selectedPlanId) return;
                            setPreviewingIntervention(true);
                            setError('');
                            try {
                              const data = await getPlanInterventionPreview(
                                selectedPlanId,
                                interventionDays,
                                interventionRemedialDays,
                              );
                              setInterventionPreview(data || null);
                            } catch (e) {
                              setError(typeof e === 'string' ? e : '获取干预预览失败');
                              setInterventionPreview(null);
                            } finally {
                              setPreviewingIntervention(false);
                            }
                          }}
                        >
                          {previewingIntervention ? '生成中...' : '生成干预预览'}
                        </button>
                        <button
                          className="plan-filter-btn"
                          disabled={!selectedPlanId || !interventionPreview || applyingPreviewPlan}
                          onClick={async () => {
                            if (!selectedPlanId || !interventionPreview) return;
                            setApplyingPreviewPlan(true);
                            setError('');
                            try {
                              await updateLearningPlanSettings(selectedPlanId, {
                                daily_minutes: Number(interventionPreview.proposed_daily_minutes || 90),
                                focus_modules: interventionPreview.top_modules || [],
                                source: 'intervention_preview',
                                note: `基于${interventionPreview.days}天健康窗口应用干预建议`,
                              });
                              setTaskGenMessage('已应用干预建议到计划设置（分钟与模块）。');
                              await refreshSelectedPlanPanels(selectedPlanId);
                            } catch (e) {
                              setError(typeof e === 'string' ? e : '应用干预建议失败');
                            } finally {
                              setApplyingPreviewPlan(false);
                            }
                          }}
                        >
                          {applyingPreviewPlan ? '应用中...' : '应用建议设置'}
                        </button>
                        <button
                          className="plan-filter-btn"
                          disabled={!selectedPlanId || !interventionPreview || applyingIntervention}
                          onClick={async () => {
                            if (!selectedPlanId || !interventionPreview) return;
                            setApplyingIntervention(true);
                            setError('');
                            try {
                              const applied = await applyPlanIntervention(
                                selectedPlanId,
                                interventionDays,
                                interventionRemedialDays,
                              );
                              setTaskGenMessage(applied?.message || '干预任务已应用');
                              await refreshSelectedPlanPanels(selectedPlanId);
                            } catch (e) {
                              setError(typeof e === 'string' ? e : '应用干预任务失败');
                            } finally {
                              setApplyingIntervention(false);
                            }
                          }}
                        >
                          {applyingIntervention ? '执行中...' : '一键应用干预任务'}
                        </button>
                        <button
                          className="plan-filter-btn"
                          disabled={!selectedPlanId || loadingPlanReminders}
                          onClick={() => loadPlanReminderSuggestions(selectedPlanId)}
                        >
                          {loadingPlanReminders ? '分析中...' : '生成提醒建议'}
                        </button>
                        <button
                          className="plan-filter-btn"
                          disabled={!selectedPlanId || !planReminderSuggestions || creatingPlanReminders}
                          onClick={async () => {
                            if (!selectedPlanId || !planReminderSuggestions) return;
                            setCreatingPlanReminders(true);
                            setError('');
                            try {
                              const selectedSources = (planReminderSuggestions.items || []).map((x) => x.source);
                              const result = await applyPlanExecutionReminders(selectedPlanId, {
                                days: interventionDays,
                                selectedSources,
                                preferredChannel: 'app',
                                dedupeLookbackHours: Number(reminderPrefs?.strategy_config?.frequency_window_hours || 12),
                              });
                              setTaskGenMessage(`已创建提醒 ${result?.created || 0} 条，跳过 ${result?.skipped || 0} 条（去重）。`);
                            } catch (e) {
                              setError(typeof e === 'string' ? e : '创建计划提醒失败');
                            } finally {
                              setCreatingPlanReminders(false);
                            }
                          }}
                        >
                          {creatingPlanReminders ? '创建中...' : '一键创建提醒'}
                        </button>
                      </div>
                    </div>
                  </div>

                  {interventionPreview && (
                    <div className="plan-loop-preview">
                      <p>
                        干预预览：健康 {interventionPreview.health_level}，建议每日
                        {' '}
                        <strong>{interventionPreview.proposed_daily_minutes}</strong>
                        {' '}分钟，优先模块：
                        {' '}
                        {(interventionPreview.top_modules || []).map(moduleLabel).join('、') || '无'}
                      </p>
                      {(interventionPreview.suggestions || []).length > 0 && (
                        <ul>
                          {(interventionPreview.suggestions || []).map((s, idx) => <li key={`${idx}_${s}`}>{s}</li>)}
                        </ul>
                      )}
                      {(interventionPreview.intervention_daily_tasks || []).length > 0 && (
                        <div className="plan-suggest-list">
                          {(interventionPreview.intervention_daily_tasks || []).map((item, idx) => (
                            <div key={`${idx}_${item.title}`} className="plan-suggest-item">
                              <span>#{idx + 1}</span>
                              <span>{moduleLabel(normalizeModule(item.module))} · {item.title}</span>
                              <span className="plan-suggest-actions">{item.time_required || 0} 分钟</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {planReminderSuggestions && (
                    <div className="plan-loop-preview">
                      <p>
                        提醒建议：{planReminderSuggestions.recommended_count || 0} 条
                        {' '}（今日待办 {planReminderSuggestions.pending_today_count || 0}，逾期 {planReminderSuggestions.overdue_count || 0}）。
                      </p>
                      <div className="plan-suggest-list">
                        {(planReminderSuggestions.items || []).map((item, idx) => (
                          <div key={`${item.source}_${idx}`} className="plan-suggest-item">
                            <span>#{idx + 1}</span>
                            <span>
                              {item.title} · {item.priority}
                              <br />
                              <span className="plan-loop-subtle">{item.content}</span>
                            </span>
                            <span className="plan-suggest-actions">{item.channel}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="plan-loop-preview">
                    <p>提醒策略配置（发送策略实时生效）</p>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                      <label>
                        频控窗口(小时)
                        <input
                          type="number"
                          min="1"
                          max="24"
                          className="plan-input"
                          style={{ width: 96, marginLeft: 6 }}
                          value={Number(reminderPrefs.strategy_config?.frequency_window_hours || 3)}
                          onChange={(e) => setReminderPrefs((prev) => ({
                            ...prev,
                            strategy_config: {
                              ...prev.strategy_config,
                              frequency_window_hours: Math.max(1, Math.min(24, Number(e.target.value) || 3)),
                            },
                          }))}
                        />
                      </label>
                      <label>
                        窗口最大提醒数
                        <input
                          type="number"
                          min="1"
                          max="10"
                          className="plan-input"
                          style={{ width: 96, marginLeft: 6 }}
                          value={Number(reminderPrefs.strategy_config?.max_reminders_per_window || 2)}
                          onChange={(e) => setReminderPrefs((prev) => ({
                            ...prev,
                            strategy_config: {
                              ...prev.strategy_config,
                              max_reminders_per_window: Math.max(1, Math.min(10, Number(e.target.value) || 2)),
                            },
                          }))}
                        />
                      </label>
                      <label>
                        偏好时段容忍(分钟)
                        <input
                          type="number"
                          min="15"
                          max="360"
                          className="plan-input"
                          style={{ width: 96, marginLeft: 6 }}
                          value={Number(reminderPrefs.strategy_config?.preferred_tolerance_minutes || 90)}
                          onChange={(e) => setReminderPrefs((prev) => ({
                            ...prev,
                            strategy_config: {
                              ...prev.strategy_config,
                              preferred_tolerance_minutes: Math.max(15, Math.min(360, Number(e.target.value) || 90)),
                            },
                          }))}
                        />
                      </label>
                      <label>
                        <input
                          type="checkbox"
                          checked={Boolean(reminderPrefs.strategy_config?.merge_similar_enabled)}
                          onChange={(e) => setReminderPrefs((prev) => ({
                            ...prev,
                            strategy_config: {
                              ...prev.strategy_config,
                              merge_similar_enabled: e.target.checked,
                            },
                          }))}
                        />
                        {' '}启用相似提醒合并
                      </label>
                      <label>
                        <input
                          type="checkbox"
                          checked={Boolean(reminderPrefs.strategy_config?.high_priority_bypass_cap)}
                          onChange={(e) => setReminderPrefs((prev) => ({
                            ...prev,
                            strategy_config: {
                              ...prev.strategy_config,
                              high_priority_bypass_cap: e.target.checked,
                            },
                          }))}
                        />
                        {' '}高优先级绕过频控
                      </label>
                    </div>
                    <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                      <button
                        className="plan-filter-btn"
                        disabled={loadingReminderPrefs}
                        onClick={loadReminderPrefs}
                      >
                        {loadingReminderPrefs ? '加载中...' : '读取当前策略'}
                      </button>
                      <button
                        className="plan-filter-btn"
                        disabled={savingReminderPrefs}
                        onClick={async () => {
                          setSavingReminderPrefs(true);
                          setError('');
                          try {
                            const payload = {
                              enabled: reminderPrefs.enabled,
                              channels: reminderPrefs.channels,
                              preferred_times: reminderPrefs.preferred_times,
                              quiet_hours: reminderPrefs.quiet_hours,
                              strategy_config: reminderPrefs.strategy_config,
                            };
                            await updateReminderPreferences(payload);
                            setTaskGenMessage('提醒策略已保存。');
                          } catch (e) {
                            setError(typeof e === 'string' ? e : '保存提醒策略失败');
                          } finally {
                            setSavingReminderPrefs(false);
                          }
                        }}
                      >
                        {savingReminderPrefs ? '保存中...' : '保存提醒策略'}
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <p className="plan-loop-subtle">请选择计划后查看健康闭环数据。</p>
              )}
            </div>

            {paceCalibration && (
              <div className="plan-reminder-panel">
                <div className="plan-reminder-head">
                  <h4>学习节奏自动校准</h4>
                  <button
                    className="plan-filter-btn"
                    disabled={calibrating || !paceCalibration.hasEnough}
                    onClick={async () => {
                      if (!selectedPlanId || !paceCalibration) return;
                      setCalibrating(true);
                      setError('');
                      try {
                        await updateLearningPlanSettings(selectedPlanId, {
                          daily_minutes: paceCalibration.nextMinutes,
                          focus_modules: paceCalibration.nextFocusModules,
                          source: 'auto_calibration',
                          note: `近3天平均执行率 ${paceCalibration.avgRate.toFixed(1)}%`,
                        });
                        setTaskGenMessage(`已应用校准：每日 ${paceCalibration.currentMinutes} -> ${paceCalibration.nextMinutes} 分钟`);
                        await loadPlans();
                        await refreshSelectedPlanPanels(selectedPlanId);
                      } catch (e) {
                        setError(typeof e === 'string' ? e : '应用节奏校准失败');
                      } finally {
                        setCalibrating(false);
                      }
                    }}
                  >
                    {calibrating ? '应用中...' : '一键应用校准'}
                  </button>
                </div>
                <div className="plan-reminder-metrics">
                  <span>近3天平均执行率：{paceCalibration.avgRate.toFixed(1)}%</span>
                  <span>当前：{paceCalibration.currentMinutes} 分钟/天</span>
                  <span>建议：{paceCalibration.nextMinutes} 分钟/天</span>
                </div>
                <p style={{ marginTop: 6 }}>{paceCalibration.reason}</p>
                {!paceCalibration.hasEnough && (
                  <p className="plan-reminder-warning">最近有效任务数据不足 2 天，先积累更多执行数据再自动校准更准确。</p>
                )}
              </div>
            )}

            {planTasks.length > 0 && (
              <div className="plan-reminder-panel">
                <div className="plan-reminder-head">
                  <h4>今日待办提醒</h4>
                  <button className="plan-filter-btn" onClick={() => setShowPendingOnly((v) => !v)}>
                    {showPendingOnly ? '显示全部任务' : '仅看未完成'}
                  </button>
                </div>
                <div className="plan-reminder-metrics">
                  <span>今日未完成：{executionReminder.todayPendingCount}</span>
                  <span>逾期未完成：{executionReminder.overduePendingCount}</span>
                  <span>剩余预计：{executionReminder.remainingMinutes} 分钟</span>
                </div>
                {executionReminder.overduePendingCount > 0 && (
                  <p className="plan-reminder-warning">有逾期任务，建议先清理旧任务再做新任务。</p>
                )}
                <div className="plan-suggest-list">
                  {executionReminder.topSuggestions.map((s, idx) => (
                    <div key={`${s.dailyId}_${s.title}`} className="plan-suggest-item">
                      <span>#{idx + 1}</span>
                      <span>{s.dayText} · {moduleLabel(s.module)} · {s.title}</span>
                      <span className="plan-suggest-actions">
                        <span>{s.timeRequired} 分钟</span>
                        <button type="button" className="plan-link-btn" onClick={() => goModuleMistakes(s.module)}>错题</button>
                        <button type="button" className="plan-link-btn" onClick={() => goModulePractice(s.module)}>练习</button>
                      </span>
                    </div>
                  ))}
                  {executionReminder.topSuggestions.length === 0 && <p>当前没有待处理任务，节奏很好。</p>}
                </div>
              </div>
            )}

            {moduleRiskRows.length > 0 && (
              <div className="plan-reminder-panel" style={{ marginTop: 0 }}>
                <div className="plan-reminder-head">
                  <h4>模块风险联动</h4>
                </div>
                <div className="plan-suggest-list">
                  {moduleRiskRows.slice(0, 4).map((row) => (
                    <div key={`${row.module}_${row.risk_score}`} className="plan-suggest-item">
                      <span>{moduleLabel(normalizeModule(row.module))}</span>
                      <span>
                        风险指数 {Number(row.risk_score || 0).toFixed(1)} · 错题 {row.mistake_count || 0} · 到期 {row.due_count || 0}
                      </span>
                      <span className="plan-suggest-actions">
                        <button type="button" className="plan-link-btn" onClick={() => goModuleMistakes(row.module)}>查看错题</button>
                        <button type="button" className="plan-link-btn" onClick={() => goModulePractice(row.module)}>去练习</button>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {planTasks.length > 0 && (
              <div className="plan-insights-grid">
                <div className="plan-insight-card">
                  <h4>近7天完成趋势</h4>
                  <div className="plan-trend-bars">
                    {weeklyTrend.map((d) => (
                      <div key={d.dayText} className="plan-trend-item" title={`${d.dayText}：${d.done}/${d.total}`}>
                        <div className={`plan-trend-bar ${d.isToday ? 'today' : ''}`}>
                          <span style={{ height: `${Math.max(4, Math.min(100, d.percent))}%` }} />
                        </div>
                        <div className="plan-trend-label">{d.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="plan-insight-card">
                  <h4>模块完成占比</h4>
                  <div className="plan-module-stats">
                    {moduleCompletionStats.map((m) => (
                      <div key={m.module} className="plan-module-row">
                        <div className="plan-module-head">
                          <span>{moduleLabel(m.module)}</span>
                          <span>
                            {m.done}/{m.total}（{m.rate.toFixed(0)}%）
                            {' '}
                            <button type="button" className="plan-link-btn" onClick={() => goModuleMistakes(m.module)}>错题</button>
                            <button type="button" className="plan-link-btn" onClick={() => goModulePractice(m.module)}>练习</button>
                          </span>
                        </div>
                        <div className="plan-module-bar">
                          <span style={{ width: `${Math.max(0, Math.min(100, m.rate))}%` }} />
                        </div>
                      </div>
                    ))}
                    {moduleCompletionStats.length === 0 && <p>暂无可统计数据</p>}
                  </div>
                </div>
              </div>
            )}

            {visibleDailyTasks.length === 0 ? (
              <p>当前计划暂无每日任务，请先点击“生成每日任务”。</p>
            ) : (
              <div style={{ display: 'grid', gap: 10 }}>
                {visibleDailyTasks.map((daily) => (
                  <div
                    key={daily.id}
                    className={`plan-day-card ${formatDate(daily.date) === todayDateText ? 'today' : ''}`}
                  >
                    <div style={{ marginBottom: 8 }}>
                      <strong>{formatDate(daily.date)}</strong>
                      {' '}
                      <span style={{ color: daily.completed ? '#0b8f83' : '#6c7a7a' }}>
                        {daily.completed ? '（当天已完成）' : '（进行中）'}
                      </span>
                      {formatDate(daily.date) === todayDateText && (
                        <span className="plan-today-badge">今日任务</span>
                      )}
                    </div>
                    <div style={{ display: 'grid', gap: 6 }}>
                      {(daily.tasks || []).map((t) => {
                        const taskKey = `${daily.id}:${t.id}`;
                        return (
                          <label key={t.id} className={`plan-task-item ${recentlyDoneTaskKey === taskKey ? 'done-pop' : ''}`}>
                            <input
                              type="checkbox"
                              checked={Boolean(t.completed)}
                              disabled={updatingTaskKey === taskKey}
                              onChange={async (e) => {
                                const checked = e.target.checked;
                                setError('');
                                setUpdatingTaskKey(taskKey);
                                try {
                                  await updatePlanTaskProgress(daily.id, {
                                    task_id: t.id,
                                    completed: checked,
                                    progress: checked ? 100 : 0,
                                    time_spent: checked ? Number(t.time_required || 0) : Number(t.time_spent || 0),
                                  });
                                  if (checked) {
                                    setRecentlyDoneTaskKey(taskKey);
                                    setTimeout(() => setRecentlyDoneTaskKey(''), 900);
                                  }
                                  await loadSelectedPlanTasks(selectedPlanId);
                                } catch (err) {
                                  setError(typeof err === 'string' ? err : '更新任务进度失败');
                                } finally {
                                  setUpdatingTaskKey('');
                                }
                              }}
                            />
                            <span>
                              <strong>{t.title}</strong>
                              <span className="plan-task-meta">
                                {moduleLabel(normalizeModule(t.module))} · {t.time_required || 0} 分钟
                              </span>
                              <br />
                              <span style={{ color: '#5b6868' }}>{t.description}</span>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Plans;
