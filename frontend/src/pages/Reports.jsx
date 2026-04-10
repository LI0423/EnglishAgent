import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import {
  getMistakeHotspots,
  getMistakeModuleComparison,
  getMistakeRecommendations,
  getMistakeReviewEffectiveness,
  getMistakeTrends,
  getMistakeWeeklyFocus,
  getPlanInterventionPreview,
  getPlanInterventionStatus,
  getPlanCalibrationLogs,
  getPlanHealthReport,
  getPlans,
  getSessionReport,
  applyPlanIntervention,
  getVocabularyStrategyInsights,
} from '../utils/api';

function Reports() {
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
    { to: '/reports', label: '📊 学习报告' },
    { to: '/plans', label: '🎯 个性化计划' },
  ];

  const [sessionId, setSessionId] = useState('');
  const [report, setReport] = useState(null);
  const [plans, setPlans] = useState([]);
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [planHealthDays, setPlanHealthDays] = useState(14);
  const [planHealth, setPlanHealth] = useState(null);
  const [planCalibrations, setPlanCalibrations] = useState([]);
  const [planInterventionDays, setPlanInterventionDays] = useState(3);
  const [planInterventionPreview, setPlanInterventionPreview] = useState(null);
  const [planInterventionStatus, setPlanInterventionStatus] = useState(null);
  const [planInterventionMessage, setPlanInterventionMessage] = useState('');
  const [applyingIntervention, setApplyingIntervention] = useState(false);
  const [trendDays, setTrendDays] = useState(7);
  const [trendModule, setTrendModule] = useState('');
  const [mistakeTrends, setMistakeTrends] = useState([]);
  const [reviewEffectiveness, setReviewEffectiveness] = useState([]);
  const [hotspotDays, setHotspotDays] = useState(14);
  const [mistakeHotspots, setMistakeHotspots] = useState([]);
  const [mistakeRecommendations, setMistakeRecommendations] = useState([]);
  const [moduleCompareDays, setModuleCompareDays] = useState(14);
  const [moduleComparison, setModuleComparison] = useState([]);
  const [weeklyFocus, setWeeklyFocus] = useState(null);
  const [strategyDays, setStrategyDays] = useState(14);
  const [strategyInsights, setStrategyInsights] = useState([]);
  const [error, setError] = useState('');

  const toDayStartTsByDays = (days) => {
    const d = Math.max(1, Number(days || 1));
    const now = Math.floor(Date.now() / 1000);
    return now - d * 24 * 3600;
  };

  const onTrendPointClick = (payload) => {
    if (!payload?.day_start) return;
    const params = new URLSearchParams();
    if (trendModule) params.set('module', trendModule);
    params.set('dayStart', String(payload.day_start));
    params.set('dayEnd', String(Number(payload.day_start) + 86399));
    navigate(`/mistakes?${params.toString()}`);
  };

  const onHotspotClick = (payload) => {
    if (!payload) return;
    const params = new URLSearchParams();
    if (payload.module) params.set('module', String(payload.module));
    if (payload.error_type) params.set('errorType', String(payload.error_type));
    const dayStart = toDayStartTsByDays(hotspotDays);
    params.set('dayStart', String(dayStart));
    params.set('dayEnd', String(Math.floor(Date.now() / 1000)));
    navigate(`/mistakes?${params.toString()}`);
  };

  const loadMistakeTrends = async (days = trendDays) => {
    try {
      const rows = await getMistakeTrends(days, trendModule || null, null);
      setMistakeTrends(rows || []);
    } catch {
      setMistakeTrends([]);
    }
  };

  const loadReviewEffectiveness = async (days = trendDays) => {
    try {
      const rows = await getMistakeReviewEffectiveness(days, trendModule || null, null);
      const normalized = (rows || []).map((item) => ({
        ...item,
        avg_mastery_gain_percent: Math.round((Number(item.avg_mastery_gain || 0) * 100) * 10) / 10,
      }));
      setReviewEffectiveness(normalized);
    } catch {
      setReviewEffectiveness([]);
    }
  };

  const loadStrategyInsights = async (days = strategyDays) => {
    try {
      const rows = await getVocabularyStrategyInsights(days);
      setStrategyInsights(rows || []);
    } catch {
      setStrategyInsights([]);
    }
  };

  const loadMistakeHotspots = async (days = hotspotDays) => {
    try {
      const rows = await getMistakeHotspots(days, trendModule || null, 30);
      setMistakeHotspots(rows || []);
    } catch {
      setMistakeHotspots([]);
    }
  };

  const loadMistakeRecommendations = async (days = hotspotDays) => {
    try {
      const rows = await getMistakeRecommendations(days, trendModule || null, 5);
      setMistakeRecommendations(rows || []);
    } catch {
      setMistakeRecommendations([]);
    }
  };

  const loadModuleComparison = async (days = moduleCompareDays) => {
    try {
      const rows = await getMistakeModuleComparison(days);
      setModuleComparison(rows || []);
    } catch {
      setModuleComparison([]);
    }
  };

  const loadWeeklyFocus = async (days = moduleCompareDays) => {
    const data = await getMistakeWeeklyFocus(days, 90);
    setWeeklyFocus(data);
  };

  const loadPlans = async () => {
    const rows = await getPlans();
    setPlans(rows || []);
    if ((rows || []).length > 0 && !selectedPlanId) {
      setSelectedPlanId(rows[0].id);
    }
  };

  const loadPlanHealth = async (days = planHealthDays, planId = selectedPlanId || null) => {
    try {
      const data = await getPlanHealthReport(planId, days);
      setPlanHealth(data || null);
    } catch {
      setPlanHealth(null);
    }
  };

  const loadPlanCalibrations = async (planId = selectedPlanId || null) => {
    try {
      const rows = await getPlanCalibrationLogs(planId, 20);
      setPlanCalibrations(rows || []);
    } catch {
      setPlanCalibrations([]);
    }
  };

  const loadInterventionPreview = async (planId = selectedPlanId || null, days = planHealthDays, remedialDays = planInterventionDays) => {
    if (!planId) {
      setPlanInterventionPreview(null);
      return;
    }
    try {
      const data = await getPlanInterventionPreview(planId, days, remedialDays);
      setPlanInterventionPreview(data || null);
    } catch {
      setPlanInterventionPreview(null);
    }
  };

  const loadInterventionStatus = async (planId = selectedPlanId || null, days = planHealthDays) => {
    try {
      const data = await getPlanInterventionStatus(planId, days);
      setPlanInterventionStatus(data || null);
    } catch {
      setPlanInterventionStatus(null);
    }
  };

  useEffect(() => {
    loadPlans();
    loadMistakeTrends(trendDays);
    loadReviewEffectiveness(trendDays);
    loadMistakeHotspots(hotspotDays);
    loadMistakeRecommendations(hotspotDays);
    loadModuleComparison(moduleCompareDays);
    loadWeeklyFocus(moduleCompareDays);
    loadStrategyInsights(strategyDays);
  }, [trendDays, trendModule, hotspotDays, strategyDays, moduleCompareDays]);

  useEffect(() => {
    loadPlanHealth(planHealthDays, selectedPlanId || null);
    loadPlanCalibrations(selectedPlanId || null);
    loadInterventionPreview(selectedPlanId || null, planHealthDays, planInterventionDays);
    loadInterventionStatus(selectedPlanId || null, planHealthDays);
  }, [selectedPlanId, planHealthDays]);

  const healthLabelMap = {
    healthy: '健康',
    watch: '需关注',
    at_risk: '高风险',
    unknown: '暂无',
  };

  const formatDateTime = (ts) => {
    if (!ts) return '-';
    const d = new Date(Number(ts) * 1000);
    if (Number.isNaN(d.getTime())) return '-';
    return d.toLocaleString();
  };

  return (
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>📊 学习报告</h1></div>
        </div>
      </header>
      <div className="main-layout">
        <div className="sidebar">
          <div className="sidebar-header"><h2>🎓 IELTS Agent</h2></div>
          <nav className="sidebar-nav">
            <ul>
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink to={item.to} end={item.to === '/'} className={({ isActive }) => `sidebar-nav-link${isActive ? ' active' : ''}`}>
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="content-area content-shell">
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>计划执行健康度（{planHealthDays}天）</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
              <select value={selectedPlanId} onChange={(e) => setSelectedPlanId(e.target.value)}>
                <option value="">自动选择最新计划</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id.slice(0, 8)} | {p.status} | {p.daily_minutes} 分钟/天
                  </option>
                ))}
              </select>
              <button onClick={() => setPlanHealthDays(7)} disabled={planHealthDays === 7}>近7天</button>
              <button onClick={() => setPlanHealthDays(14)} disabled={planHealthDays === 14}>近14天</button>
              <button onClick={() => setPlanHealthDays(30)} disabled={planHealthDays === 30}>近30天</button>
              <button onClick={() => { loadPlanHealth(planHealthDays, selectedPlanId || null); loadPlanCalibrations(selectedPlanId || null); }}>
                刷新计划健康度
              </button>
            </div>
            {planHealth && planHealth.plan_id ? (
              <>
                <p>
                  健康等级：<strong>{healthLabelMap[planHealth.health_level] || planHealth.health_level}</strong>
                  {' '}| 连续完成天数：<strong>{planHealth.streak_days}</strong>
                  {' '}| 任务完成率：<strong>{Number(planHealth.task_completion_rate || 0).toFixed(1)}%</strong>
                  {' '}| 天完成率：<strong>{Number(planHealth.day_completion_rate || 0).toFixed(1)}%</strong>
                </p>
                <p>
                  执行量：{planHealth.task_done}/{planHealth.task_total}，
                  完整完成天数：{planHealth.completed_days}/{planHealth.scheduled_days}，
                  每日计划时长：{planHealth.daily_minutes} 分钟
                </p>
                <div style={{ width: '100%', height: 260, marginTop: 8 }}>
                  <ResponsiveContainer>
                    <LineChart data={planHealth.daily_trend || []}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis yAxisId="left" allowDecimals={false} />
                      <YAxis yAxisId="right" orientation="right" />
                      <Tooltip />
                      <Legend />
                      <Line yAxisId="left" type="monotone" dataKey="done" name="已完成任务数" stroke="#50CD89" strokeWidth={2} />
                      <Line yAxisId="left" type="monotone" dataKey="total" name="计划任务数" stroke="#009EF7" strokeWidth={2} />
                      <Line yAxisId="right" type="monotone" dataKey="completion_rate" name="当日完成率(%)" stroke="#F1416C" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ width: '100%', height: 240, marginTop: 8 }}>
                  <ResponsiveContainer>
                    <BarChart data={planHealth.module_stats || []}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="module" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="done" name="已完成任务" fill="#50CD89" />
                      <Bar dataKey="total" name="计划任务" fill="#009EF7" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : (
              <p>暂无计划执行健康度数据。</p>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>计划校准历史</h3>
            {planCalibrations.length > 0 ? (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th align="left">时间</th>
                    <th align="left">来源</th>
                    <th align="left">分钟调整</th>
                    <th align="left">模块调整</th>
                    <th align="left">备注</th>
                  </tr>
                </thead>
                <tbody>
                  {planCalibrations.map((x) => (
                    <tr key={x.id}>
                      <td>{formatDateTime(x.created_at)}</td>
                      <td>{x.source}</td>
                      <td>{x.before_daily_minutes ?? '-'} → {x.after_daily_minutes ?? '-'}</td>
                      <td>
                        {(x.before_focus_modules || []).join('/') || '-'}
                        {' '}→{' '}
                        {(x.after_focus_modules || []).join('/') || '-'}
                      </td>
                      <td>{x.note || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p>暂无校准历史（手动/自动调整计划后会记录）。</p>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>主动干预建议</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
              <label>补救天数：</label>
              <select value={planInterventionDays} onChange={(e) => setPlanInterventionDays(Number(e.target.value) || 3)}>
                <option value={2}>2天</option>
                <option value={3}>3天</option>
                <option value={5}>5天</option>
                <option value={7}>7天</option>
              </select>
              <button onClick={() => loadInterventionPreview(selectedPlanId || null, planHealthDays, planInterventionDays)}>
                刷新干预建议
              </button>
              <button
                disabled={!selectedPlanId || applyingIntervention}
                onClick={async () => {
                  if (!selectedPlanId) return;
                  setApplyingIntervention(true);
                  setPlanInterventionMessage('');
                  try {
                    const result = await applyPlanIntervention(selectedPlanId, planHealthDays, planInterventionDays);
                    setPlanInterventionMessage(result?.message || '已应用干预任务');
                    await loadPlanHealth(planHealthDays, selectedPlanId);
                    await loadInterventionPreview(selectedPlanId, planHealthDays, planInterventionDays);
                    await loadInterventionStatus(selectedPlanId, planHealthDays);
                  } catch (e) {
                    setPlanInterventionMessage(typeof e === 'string' ? e : '应用干预失败');
                  } finally {
                    setApplyingIntervention(false);
                  }
                }}
              >
                {applyingIntervention ? '应用中...' : '一键应用干预'}
              </button>
            </div>
            {planInterventionPreview ? (
              <>
                <p>目标计划：{planInterventionPreview.plan_id?.slice(0, 8)}，风险等级：{healthLabelMap[planInterventionPreview.health_level] || planInterventionPreview.health_level}</p>
                <p>建议日分钟：{planInterventionPreview.proposed_daily_minutes} 分钟，近阶段任务完成率：{Number(planInterventionPreview.task_completion_rate || 0).toFixed(1)}%</p>
                <p>优先模块：{(planInterventionPreview.top_modules || []).join(' / ') || '—'}</p>
                <ul>
                  {(planInterventionPreview.suggestions || []).map((s, idx) => <li key={idx}>{s}</li>)}
                </ul>
                <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th align="left">模块</th>
                      <th align="left">补救任务</th>
                      <th align="left">时长</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(planInterventionPreview.intervention_daily_tasks || []).map((x, idx) => (
                      <tr key={`${x.module}_${idx}`}>
                        <td>{x.module}</td>
                        <td>{x.title}</td>
                        <td>{x.time_required} 分钟</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <p>暂无干预建议。先选择计划并生成任务数据后再查看。</p>
            )}
            {planInterventionMessage && <p style={{ marginTop: 8, color: '#0f766e' }}>{planInterventionMessage}</p>}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>干预执行追踪</h3>
            {planInterventionStatus && planInterventionStatus.plan_id ? (
              <>
                <p>
                  累计干预任务：{planInterventionStatus.intervention_done}/{planInterventionStatus.intervention_total}
                  {' '}（完成率 {Number(planInterventionStatus.intervention_completion_rate || 0).toFixed(1)}%）
                </p>
                <p>
                  干预批次数：{planInterventionStatus.batch_count}，
                  最近批次：{planInterventionStatus.latest_batch_id ? planInterventionStatus.latest_batch_id.slice(0, 8) : '—'}
                </p>
                <div style={{ width: '100%', height: 250, marginTop: 8 }}>
                  <ResponsiveContainer>
                    <LineChart data={planInterventionStatus.daily_trend || []}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis yAxisId="left" allowDecimals={false} />
                      <YAxis yAxisId="right" orientation="right" />
                      <Tooltip />
                      <Legend />
                      <Line yAxisId="left" type="monotone" dataKey="done" name="已完成干预任务" stroke="#50CD89" strokeWidth={2} />
                      <Line yAxisId="left" type="monotone" dataKey="total" name="干预任务总数" stroke="#009EF7" strokeWidth={2} />
                      <Line yAxisId="right" type="monotone" dataKey="completion_rate" name="干预完成率(%)" stroke="#F1416C" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ width: '100%', height: 240, marginTop: 8 }}>
                  <ResponsiveContainer>
                    <BarChart data={planInterventionStatus.module_stats || []}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="module" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="done" name="已完成干预" fill="#50CD89" />
                      <Bar dataKey="total" name="干预总量" fill="#7239EA" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : (
              <p>暂无干预执行数据，应用一次干预计划后会显示追踪结果。</p>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>查询会话报告</h3>
            <input
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="输入 session_id"
              style={{ width: '100%', marginBottom: 8 }}
            />
            <button
              onClick={async () => {
                setError('');
                try {
                  setReport(await getSessionReport(sessionId.trim()));
                } catch (e) {
                  setError(typeof e === 'string' ? e : '查询失败');
                  setReport(null);
                }
              }}
              disabled={!sessionId.trim()}
            >
              获取报告
            </button>
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>错题趋势（{trendDays}天{trendModule ? ` · ${trendModule}` : ' · 全模块'}）</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button onClick={() => setTrendDays(7)} disabled={trendDays === 7}>近7天</button>
              <button onClick={() => setTrendDays(30)} disabled={trendDays === 30}>近30天</button>
              <select value={trendModule} onChange={(e) => setTrendModule(e.target.value)}>
                <option value="">全部模块</option>
                <option value="listening">听力</option>
                <option value="reading">阅读</option>
                <option value="writing">写作</option>
                <option value="speaking">口语</option>
                <option value="vocabulary">词汇</option>
              </select>
              <button onClick={() => loadMistakeTrends(trendDays)}>刷新趋势</button>
              <button onClick={() => loadReviewEffectiveness(trendDays)}>刷新复习成效</button>
            </div>
            {mistakeTrends.length > 0 ? (
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer>
                  <LineChart
                    data={mistakeTrends}
                    onClick={(state) => {
                      const row = state?.activePayload?.[0]?.payload;
                      if (row) onTrendPointClick(row);
                    }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="created_count" name="新增错题" stroke="#4A6CF7" strokeWidth={2} />
                    <Line type="monotone" dataKey="reviewed_count" name="完成复习" stroke="#50CD89" strokeWidth={2} />
                    <Line type="monotone" dataKey="due_snapshot" name="到期存量" stroke="#F1416C" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p>暂无趋势数据</p>
            )}
            <p style={{ fontSize: 12, color: '#666', marginTop: 8 }}>
              提示：点击图表中的某一天，可跳转错题页查看当日明细。
            </p>
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>复习成效（{trendDays}天{trendModule ? ` · ${trendModule}` : ' · 全模块'}）</h3>
            {reviewEffectiveness.length > 0 ? (
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer>
                  <LineChart data={reviewEffectiveness}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis yAxisId="left" allowDecimals={false} />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend />
                    <Line yAxisId="left" type="monotone" dataKey="review_count" name="复习次数" stroke="#009EF7" strokeWidth={2} />
                    <Line yAxisId="right" type="monotone" dataKey="avg_mastery_gain_percent" name="平均掌握度增益(%)" stroke="#FFC700" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p>暂无复习成效数据</p>
            )}
            <p style={{ fontSize: 12, color: '#666', marginTop: 8 }}>
              说明：掌握度增益 = 本次复习后掌握度 - 复习前掌握度。
            </p>
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>错因热区（模块×错因）</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button onClick={() => setHotspotDays(7)} disabled={hotspotDays === 7}>近7天</button>
              <button onClick={() => setHotspotDays(14)} disabled={hotspotDays === 14}>近14天</button>
              <button onClick={() => setHotspotDays(30)} disabled={hotspotDays === 30}>近30天</button>
              <button onClick={() => loadMistakeHotspots(hotspotDays)}>刷新热区</button>
              <button onClick={() => loadMistakeRecommendations(hotspotDays)}>刷新建议</button>
            </div>
            {mistakeHotspots.length > 0 ? (
              <>
                <div style={{ width: '100%', height: 280 }}>
                  <ResponsiveContainer>
                    <BarChart
                      data={mistakeHotspots.slice(0, 12)}
                      onClick={(state) => {
                        const row = state?.activePayload?.[0]?.payload;
                        if (row) onHotspotClick(row);
                      }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="error_type" hide />
                      <YAxis />
                      <Tooltip formatter={(value, name, item) => [value, name]} labelFormatter={(_, payload) => {
                        const row = payload?.[0]?.payload;
                        return row ? `${row.module} · ${row.error_type}` : '';
                      }} />
                      <Legend />
                      <Bar dataKey="count" name="错题数" fill="#F1416C" />
                      <Bar dataKey="due_count" name="到期数" fill="#FFC700" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ marginTop: 8 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        <th align="left">模块</th>
                        <th align="left">错因</th>
                        <th align="left">错题数</th>
                        <th align="left">到期数</th>
                        <th align="left">平均掌握度</th>
                        <th align="left">风险分</th>
                        <th align="left">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mistakeHotspots.slice(0, 10).map((x, idx) => (
                        <tr key={`${x.module}_${x.error_type}_${idx}`}>
                          <td>{x.module}</td>
                          <td>{x.error_type}</td>
                          <td>{x.count}</td>
                          <td>{x.due_count}</td>
                          <td>{Math.round((Number(x.avg_mastery || 0)) * 100)}%</td>
                          <td>{Number(x.risk_score || 0).toFixed(3)}</td>
                          <td>
                            <button onClick={() => onHotspotClick(x)}>去练这一类</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div style={{ marginTop: 10, padding: 12, background: '#f8fafc', borderRadius: 8 }}>
                  <h4 style={{ marginBottom: 8 }}>自动训练建议（基于热区风险）</h4>
                  {mistakeRecommendations.length > 0 ? (
                    <>
                      <p style={{ marginBottom: 6 }}>
                        当前优先突破：<strong>{mistakeRecommendations[0].module} · {mistakeRecommendations[0].error_type}</strong>
                      </p>
                      <p style={{ marginBottom: 6 }}>建议顺序：</p>
                      {mistakeRecommendations.map((x) => (
                        <p key={`${x.rank}_${x.module}_${x.error_type}`} style={{ marginBottom: 4 }}>
                          {x.rank}. {x.module} · {x.error_type}
                          {' '}（风险 {Number(x.risk_score || 0).toFixed(3)}，错题 {x.mistake_count}，到期 {x.due_count}）
                          {' '}→ {x.action}
                        </p>
                      ))}
                      <button
                        style={{ marginTop: 8 }}
                        onClick={() => onHotspotClick({ module: mistakeRecommendations[0].module, error_type: mistakeRecommendations[0].error_type })}
                      >
                        一键开始第一优先项训练
                      </button>
                    </>
                  ) : (
                    <p>暂无自动建议，先完成几次练习后会生成。</p>
                  )}
                </div>
              </>
            ) : (
              <p>暂无错因热区数据。</p>
            )}
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>跨模块错因分布对比</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button onClick={() => setModuleCompareDays(7)} disabled={moduleCompareDays === 7}>近7天</button>
              <button onClick={() => setModuleCompareDays(14)} disabled={moduleCompareDays === 14}>近14天</button>
              <button onClick={() => setModuleCompareDays(30)} disabled={moduleCompareDays === 30}>近30天</button>
              <button onClick={() => loadModuleComparison(moduleCompareDays)}>刷新模块对比</button>
              <button onClick={() => loadWeeklyFocus(moduleCompareDays)}>刷新周计划</button>
            </div>
            {moduleComparison.length > 0 ? (
              <>
                <div style={{ width: '100%', height: 280 }}>
                  <ResponsiveContainer>
                    <BarChart data={moduleComparison}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="module" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="count" name="错题数" fill="#009EF7" />
                      <Bar dataKey="due_count" name="到期数" fill="#F1416C" />
                      <Bar dataKey="unique_error_types" name="错因覆盖数" fill="#50CD89" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ marginTop: 8 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        <th align="left">模块</th>
                        <th align="left">错题数</th>
                        <th align="left">到期数</th>
                        <th align="left">错因覆盖数</th>
                        <th align="left">平均掌握度</th>
                        <th align="left">风险指数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {moduleComparison.map((x) => (
                        <tr key={x.module}>
                          <td>{x.module}</td>
                          <td>{x.count}</td>
                          <td>{x.due_count}</td>
                          <td>{x.unique_error_types}</td>
                          <td>{Math.round((Number(x.avg_mastery || 0)) * 100)}%</td>
                          <td>{Number(x.risk_index || 0).toFixed(3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {weeklyFocus && (
                  <div style={{ marginTop: 10, padding: 12, background: '#f8fafc', borderRadius: 8 }}>
                    <h4 style={{ marginBottom: 8 }}>本周主攻模块计划</h4>
                    <p style={{ marginBottom: 6 }}>
                      主攻模块：<strong>{weeklyFocus.focus_module || '—'}</strong>
                    </p>
                    <p style={{ marginBottom: 6 }}>
                      {weeklyFocus.summary || ''}
                    </p>
                    {(weeklyFocus.module_allocations || []).map((x) => (
                      <p key={`${x.module}_${x.percent}`} style={{ marginBottom: 4 }}>
                        {x.module}: {x.percent}%（约 {x.minutes} 分钟/天）· {x.reason}
                      </p>
                    ))}
                    {weeklyFocus.focus_module && (
                      <button
                        style={{ marginTop: 8 }}
                        onClick={() => {
                          const params = new URLSearchParams();
                          params.set('module', String(weeklyFocus.focus_module));
                          params.set('dayStart', String(Math.floor(Date.now() / 1000) - moduleCompareDays * 24 * 3600));
                          params.set('dayEnd', String(Math.floor(Date.now() / 1000)));
                          navigate(`/mistakes?${params.toString()}`);
                        }}
                      >
                        一键进入主攻模块错题
                      </button>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p>暂无跨模块对比数据。</p>
            )}
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>词汇策略效果对比（近{strategyDays}天）</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button onClick={() => setStrategyDays(7)} disabled={strategyDays === 7}>近7天</button>
              <button onClick={() => setStrategyDays(14)} disabled={strategyDays === 14}>近14天</button>
              <button onClick={() => setStrategyDays(30)} disabled={strategyDays === 30}>近30天</button>
              <button onClick={() => loadStrategyInsights(strategyDays)}>刷新策略</button>
            </div>
            {strategyInsights.length > 0 ? (
              <>
                <div style={{ width: '100%', height: 280 }}>
                  <ResponsiveContainer>
                    <BarChart data={strategyInsights}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="strategy" />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="session_count" name="会话数" fill="#009EF7" />
                      <Bar dataKey="total_words" name="学习词数" fill="#50CD89" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ width: '100%', height: 260, marginTop: 10 }}>
                  <ResponsiveContainer>
                    <BarChart data={strategyInsights}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="strategy" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="review_events_7d" name="7日复习事件" fill="#7239EA" />
                      <Bar dataKey="wrong_count_7d" name="7日错题回流" fill="#F1416C" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ marginTop: 8, fontSize: 13, color: '#666' }}>
                  {strategyInsights.map((x) => (
                    <p key={x.strategy}>
                      {x.strategy}: 平均调度分 {Number(x.avg_scheduler_score || 0).toFixed(3)}，平均掌握度 {Math.round((Number(x.avg_mastery || 0)) * 100)}%，
                      7日掌握度增益 {Math.round((Number(x.avg_mastery_gain_7d || 0)) * 1000) / 10}% ，错题回流率 {Math.round((Number(x.wrong_rate_7d || 0)) * 1000) / 10}%
                    </p>
                  ))}
                </div>
                {(() => {
                  const sorted = [...strategyInsights].sort((a, b) => {
                    const gainDiff = Number(b.avg_mastery_gain_7d || 0) - Number(a.avg_mastery_gain_7d || 0);
                    if (Math.abs(gainDiff) > 1e-9) return gainDiff;
                    return Number(a.wrong_rate_7d || 0) - Number(b.wrong_rate_7d || 0);
                  });
                  const best = sorted[0];
                  return best ? (
                    <p style={{ marginTop: 8, fontSize: 13, color: '#1f2937' }}>
                      建议：下一阶段优先使用 <strong>{best.strategy}</strong> 策略（当前表现为更高增益/更低回流）。
                    </p>
                  ) : null;
                })()}
              </>
            ) : (
              <p>暂无策略对比数据。先在词汇页开启几次学习会话后再查看。</p>
            )}
          </div>
          <div className="card">
            <h3>报告结果</h3>
            {report ? (
              <div>
                <p>{report.summary}</p>
                <p>scores: {JSON.stringify(report.scores)}</p>
                <h4>suggestions</h4>
                <ul>{(report.suggestions || []).map((s, idx) => <li key={idx}>{s}</li>)}</ul>
              </div>
            ) : (
              <p>暂无报告</p>
            )}
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Reports;
