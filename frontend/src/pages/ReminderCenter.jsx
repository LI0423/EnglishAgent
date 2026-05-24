import { useEffect, useMemo, useState } from 'react';
import SidebarMenu from '../components/layout/SidebarMenu';
import {
  applyReminderPreferencePreset,
  batchDeleteUserReminders,
  batchUpdateUserReminderStatus,
  deleteUserReminder,
  getReminderAnalyticsSummary,
  getReminderAuditLogs,
  getReminderPreferenceHistory,
  getReminderPreferencePresets,
  getReminderPreferences,
  getUserReminders,
  rollbackReminderPreference,
  updateReminderPreferences,
  updateUserReminderStatus,
} from '../utils/api';

import TopNav from "../components/layout/TopNav";
const STATUS_LABEL_MAP = {
  pending: '待发送',
  sent: '已发送',
  failed: '发送失败',
  merged: '已合并',
};

const ACTION_LABEL_MAP = {
  create: '创建提醒',
  status_update: '状态更新',
  batch_status_update: '批量状态更新',
  delete: '删除提醒',
  batch_delete: '批量删除',
  plan_apply_create: '计划建议创建',
  preference_update: '偏好配置更新',
  preference_preset_apply: '应用策略预设',
  preference_rollback: '偏好配置回滚',
};

function ReminderCenter() {

  const [statusFilter, setStatusFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [reminders, setReminders] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [preferences, setPreferences] = useState(null);
  const [preferencePresets, setPreferencePresets] = useState([]);
  const [selectedPresetKey, setSelectedPresetKey] = useState('');
  const [preferenceHistory, setPreferenceHistory] = useState([]);
  const [preferenceForm, setPreferenceForm] = useState({
    enabled: true,
    channels: ['app'],
    preferred_times: '',
    quiet_start: '23:00',
    quiet_end: '07:00',
    frequency_window_hours: 3,
    max_reminders_per_window: 2,
    preferred_tolerance_minutes: 90,
    merge_similar_enabled: true,
    high_priority_bypass_cap: false,
  });
  const [analyticsDays, setAnalyticsDays] = useState(14);
  const [analytics, setAnalytics] = useState(null);
  const [selectedTrendDay, setSelectedTrendDay] = useState('');
  const [auditActionFilter, setAuditActionFilter] = useState('all');
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [batching, setBatching] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [applyingPreset, setApplyingPreset] = useState(false);
  const [rollingBackHistoryId, setRollingBackHistoryId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const loadData = async (status = statusFilter, days = analyticsDays, action = auditActionFilter) => {
    setLoading(true);
    setError('');
    try {
      const [rows, prefs, analyticsData, auditData, presets, prefHistory] = await Promise.all([
        getUserReminders(status === 'all' ? null : status),
        getReminderPreferences(),
        getReminderAnalyticsSummary(days),
        getReminderAuditLogs(80, action === 'all' ? null : action),
        getReminderPreferencePresets(),
        getReminderPreferenceHistory(30),
      ]);
      setReminders(Array.isArray(rows) ? rows : []);
      setPreferences(prefs || null);
      setAnalytics(analyticsData || null);
      setAuditLogs(Array.isArray(auditData) ? auditData : []);
      setPreferencePresets(Array.isArray(presets) ? presets : []);
      setPreferenceHistory(Array.isArray(prefHistory) ? prefHistory : []);
      setSelectedIds([]);
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载提醒数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData('all', analyticsDays, auditActionFilter);
  }, []);

  useEffect(() => {
    if (!preferences) return;
    const cfg = preferences?.strategy_config || {};
    setPreferenceForm({
      enabled: Boolean(preferences.enabled),
      channels: Array.isArray(preferences.channels) && preferences.channels.length > 0 ? preferences.channels : ['app'],
      preferred_times: Array.isArray(preferences.preferred_times) ? preferences.preferred_times.join(', ') : '',
      quiet_start: String(preferences?.quiet_hours?.start || '23:00'),
      quiet_end: String(preferences?.quiet_hours?.end || '07:00'),
      frequency_window_hours: Number(cfg.frequency_window_hours || 3),
      max_reminders_per_window: Number(cfg.max_reminders_per_window || 2),
      preferred_tolerance_minutes: Number(cfg.preferred_tolerance_minutes || 90),
      merge_similar_enabled: Boolean(cfg.merge_similar_enabled !== false),
      high_priority_bypass_cap: Boolean(cfg.high_priority_bypass_cap),
    });
  }, [preferences]);

  const sourceOptions = useMemo(() => {
    const set = new Set();
    reminders.forEach((r) => {
      const source = String(r?.metadata?.source || '').trim();
      if (source) set.add(source);
    });
    return Array.from(set);
  }, [reminders]);

  const stats = useMemo(() => {
    const map = {
      total: reminders.length,
      pending: 0,
      sent: 0,
      failed: 0,
      merged: 0,
    };
    reminders.forEach((r) => {
      const key = String(r.status || '').toLowerCase();
      if (Object.prototype.hasOwnProperty.call(map, key)) {
        map[key] += 1;
      }
    });
    return map;
  }, [reminders]);

  const filteredRows = useMemo(() => {
    return reminders.filter((r) => {
      if (sourceFilter !== 'all') {
        const source = String(r?.metadata?.source || '').trim();
        if (source !== sourceFilter) return false;
      }
      if (selectedTrendDay) {
        const createdAt = Number(r.created_at || 0);
        if (!createdAt) return false;
        const d = new Date(createdAt * 1000);
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const rowDay = `${y}-${m}-${day}`;
        if (rowDay !== selectedTrendDay) return false;
      }
      return true;
    });
  }, [reminders, sourceFilter, selectedTrendDay]);

  const isAllSelected = filteredRows.length > 0 && filteredRows.every((r) => selectedIds.includes(r.id));

  const toggleRow = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleAll = () => {
    if (isAllSelected) {
      setSelectedIds((prev) => prev.filter((id) => !filteredRows.some((r) => r.id === id)));
      return;
    }
    const ids = filteredRows.map((r) => r.id);
    setSelectedIds((prev) => Array.from(new Set([...prev, ...ids])));
  };

  const runBatch = async (runner, successMsgBuilder) => {
    if (selectedIds.length === 0 || batching) return;
    setBatching(true);
    setError('');
    setMessage('');
    try {
      const result = await runner(selectedIds);
      const successMsg = typeof successMsgBuilder === 'function' ? successMsgBuilder(result || {}) : String(successMsgBuilder || '操作成功');
      setMessage(successMsg);
      await loadData(statusFilter, analyticsDays, auditActionFilter);
    } catch (e) {
      setError(typeof e === 'string' ? e : '批量操作失败');
    } finally {
      setBatching(false);
    }
  };

  const handleBatchStatus = async (status, label) => {
    await runBatch(
      async (ids) => batchUpdateUserReminderStatus(ids, status),
      (res) => `${label}完成：成功 ${Number(res.updated || 0)}，跳过 ${Number(res.skipped || 0)}，失败 ${Number(res.failed || 0)}。`,
    );
  };

  const handleBatchDelete = async () => {
    if (!window.confirm(`确认删除选中的 ${selectedIds.length} 条提醒吗？此操作不可恢复。`)) return;
    await runBatch(
      async (ids) => batchDeleteUserReminders(ids),
      (res) => `批量删除完成：成功 ${Number(res.deleted || 0)}，跳过 ${Number(res.skipped || 0)}，失败 ${Number(res.failed || 0)}。`,
    );
  };

  const handleRetryFailed = async () => {
    const failedIds = filteredRows.filter((r) => String(r.status || '') === 'failed').map((r) => r.id);
    if (failedIds.length === 0 || batching) {
      setMessage('当前筛选结果没有可重试的失败提醒。');
      return;
    }
    setBatching(true);
    setError('');
    setMessage('');
    try {
      const res = await batchUpdateUserReminderStatus(failedIds, 'pending');
      setMessage(`重试队列已恢复：成功 ${Number(res.updated || 0)}，跳过 ${Number(res.skipped || 0)}，失败 ${Number(res.failed || 0)}。`);
      await loadData(statusFilter, analyticsDays, auditActionFilter);
    } catch (e) {
      setError(typeof e === 'string' ? e : '重试失败提醒时出错');
    } finally {
      setBatching(false);
    }
  };

  const handleSingleStatus = async (reminderId, status) => {
    try {
      setError('');
      setMessage('');
      await updateUserReminderStatus(reminderId, status);
      setMessage(status === 'sent' ? '已标记为已发送。' : '已恢复为待发送。');
      await loadData(statusFilter, analyticsDays, auditActionFilter);
    } catch (e) {
      setError(typeof e === 'string' ? e : '更新提醒状态失败');
    }
  };

  const handleSingleDelete = async (reminderId) => {
    if (!window.confirm('确认删除该提醒吗？此操作不可恢复。')) return;
    try {
      setError('');
      setMessage('');
      await deleteUserReminder(reminderId);
      setMessage('提醒删除成功。');
      await loadData(statusFilter, analyticsDays, auditActionFilter);
    } catch (e) {
      setError(typeof e === 'string' ? e : '删除提醒失败');
    }
  };

  const handlePreferenceField = (field, value) => {
    setPreferenceForm((prev) => ({ ...prev, [field]: value }));
  };

  const toggleChannel = (channel) => {
    setPreferenceForm((prev) => {
      const exists = prev.channels.includes(channel);
      const next = exists ? prev.channels.filter((x) => x !== channel) : [...prev.channels, channel];
      return { ...prev, channels: next.length > 0 ? next : ['app'] };
    });
  };

  const savePreferences = async () => {
    setSavingPrefs(true);
    setError('');
    setMessage('');
    try {
      const times = String(preferenceForm.preferred_times || '')
        .split(',')
        .map((x) => x.trim())
        .filter((x) => /^\d{2}:\d{2}$/.test(x));
      const payload = {
        enabled: Boolean(preferenceForm.enabled),
        channels: preferenceForm.channels,
        preferred_times: times,
        quiet_hours: {
          start: preferenceForm.quiet_start || '23:00',
          end: preferenceForm.quiet_end || '07:00',
        },
        strategy_config: {
          frequency_window_hours: Math.max(1, Number(preferenceForm.frequency_window_hours || 3)),
          max_reminders_per_window: Math.max(1, Number(preferenceForm.max_reminders_per_window || 2)),
          preferred_tolerance_minutes: Math.max(15, Number(preferenceForm.preferred_tolerance_minutes || 90)),
          merge_similar_enabled: Boolean(preferenceForm.merge_similar_enabled),
          high_priority_bypass_cap: Boolean(preferenceForm.high_priority_bypass_cap),
        },
      };
      const saved = await updateReminderPreferences(payload);
      setPreferences(saved || null);
      setMessage('提醒策略保存成功。');
      await loadData(statusFilter, analyticsDays, auditActionFilter);
    } catch (e) {
      setError(typeof e === 'string' ? e : '保存提醒策略失败');
    } finally {
      setSavingPrefs(false);
    }
  };

  const applyPreset = async () => {
    if (!selectedPresetKey || applyingPreset) return;
    const preset = preferencePresets.find((item) => item.key === selectedPresetKey);
    if (!preset) {
      setError('预设不存在，请刷新后重试。');
      return;
    }
    if (!window.confirm(`确认应用预设「${preset.name}」吗？当前配置会被覆盖。`)) return;
    setApplyingPreset(true);
    setError('');
    setMessage('');
    try {
      const saved = await applyReminderPreferencePreset(selectedPresetKey);
      setPreferences(saved || null);
      setMessage(`已应用预设：${preset.name}`);
      await loadData(statusFilter, analyticsDays, auditActionFilter);
    } catch (e) {
      setError(typeof e === 'string' ? e : '应用预设失败');
    } finally {
      setApplyingPreset(false);
    }
  };

  const rollbackByHistory = async (history) => {
    const historyId = String(history?.id || '');
    if (!historyId) return;
    if (!window.confirm('确认回滚到该次变更前的配置吗？当前设置会被覆盖。')) return;
    setRollingBackHistoryId(historyId);
    setError('');
    setMessage('');
    try {
      const saved = await rollbackReminderPreference(historyId);
      setPreferences(saved || null);
      setMessage('配置已回滚。');
      await loadData(statusFilter, analyticsDays, auditActionFilter);
    } catch (e) {
      setError(typeof e === 'string' ? e : '回滚配置失败');
    } finally {
      setRollingBackHistoryId('');
    }
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

  const maxTrend = useMemo(() => {
    const rows = Array.isArray(analytics?.trend) ? analytics.trend : [];
    let m = 0;
    rows.forEach((r) => {
      m = Math.max(m, Number(r.created || 0), Number(r.sent || 0), Number(r.failed || 0), Number(r.merged || 0));
    });
    return m || 1;
  }, [analytics]);

  const formatStatusLabel = (status) => STATUS_LABEL_MAP[String(status || '').toLowerCase()] || String(status || '-');
  const formatActionLabel = (action) => ACTION_LABEL_MAP[String(action || '').toLowerCase()] || String(action || '-');
  const formatPrefSourceLabel = (source) => {
    const key = String(source || '');
    if (key === 'manual_update') return '手动保存';
    if (key === 'rollback') return '配置回滚';
    if (key.startsWith('preset:')) return `预设应用（${key.slice(7)}）`;
    return key || '-';
  };

  return (
    <div className="home-page web-dashboard reminder-page">
      <TopNav />
      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>

        <div className="content-area content-shell">
          <div className="web-page-head">
            <div>
              <h2>提醒中心</h2>
              <p>提醒队列、策略偏好、审计日志与成效分析统一管理。</p>
            </div>
            <div className="web-page-head-actions">
              <button className="plan-filter-btn" onClick={() => loadData(statusFilter, analyticsDays, auditActionFilter)} disabled={loading}>
                {loading ? '刷新中...' : '刷新数据'}
              </button>
            </div>
          </div>
          <div className="card reminder-head-card">
            <h3>提醒策略效果概览</h3>
            <div className="reminder-stats-grid">
              <div className="reminder-stat"><span>总提醒</span><strong>{stats.total}</strong></div>
              <div className="reminder-stat"><span>待发送</span><strong>{stats.pending}</strong></div>
              <div className="reminder-stat"><span>已发送</span><strong>{stats.sent}</strong></div>
              <div className="reminder-stat"><span>失败/合并</span><strong>{stats.failed + stats.merged}</strong></div>
            </div>
            {analytics && (
              <p className="reminder-subtle">
                统计窗口：近 {analytics.days} 天，来源数 {Array.isArray(analytics.source_counts) ? analytics.source_counts.length : 0}
              </p>
            )}
            {preferences && (
              <p className="reminder-subtle">
                当前策略：窗口 {Number(preferences?.strategy_config?.frequency_window_hours || 3)} 小时，
                上限 {Number(preferences?.strategy_config?.max_reminders_per_window || 2)} 条，
                合并 {String(Boolean(preferences?.strategy_config?.merge_similar_enabled))}
              </p>
            )}
          </div>

          <div className="card">
            <h3>提醒策略设置</h3>
            <div className="reminder-preset-row">
              <label>
                策略预设
                <select
                  className="plan-input"
                  value={selectedPresetKey}
                  onChange={(e) => setSelectedPresetKey(e.target.value)}
                >
                  <option value="">请选择预设</option>
                  {preferencePresets.map((preset) => (
                    <option key={preset.key} value={preset.key}>{preset.name}</option>
                  ))}
                </select>
              </label>
              <button
                className="plan-filter-btn"
                type="button"
                onClick={applyPreset}
                disabled={!selectedPresetKey || applyingPreset}
              >
                {applyingPreset ? '应用中...' : '应用预设'}
              </button>
              {selectedPresetKey && (
                <p className="reminder-subtle">
                  {String(preferencePresets.find((x) => x.key === selectedPresetKey)?.description || '')}
                </p>
              )}
            </div>
            <div className="reminder-pref-grid">
              <label>
                <span>启用提醒</span>
                <input
                  type="checkbox"
                  checked={Boolean(preferenceForm.enabled)}
                  onChange={(e) => handlePreferenceField('enabled', e.target.checked)}
                />
              </label>

              <label>
                <span>偏好时间（逗号分隔）</span>
                <input
                  className="plan-input"
                  value={preferenceForm.preferred_times}
                  onChange={(e) => handlePreferenceField('preferred_times', e.target.value)}
                  placeholder="例如 09:00, 20:30"
                />
              </label>

              <label>
                <span>静默开始</span>
                <input
                  type="time"
                  className="plan-input"
                  value={preferenceForm.quiet_start}
                  onChange={(e) => handlePreferenceField('quiet_start', e.target.value)}
                />
              </label>

              <label>
                <span>静默结束</span>
                <input
                  type="time"
                  className="plan-input"
                  value={preferenceForm.quiet_end}
                  onChange={(e) => handlePreferenceField('quiet_end', e.target.value)}
                />
              </label>

              <label>
                <span>频率窗口（小时）</span>
                <input
                  type="number"
                  min={1}
                  className="plan-input"
                  value={preferenceForm.frequency_window_hours}
                  onChange={(e) => handlePreferenceField('frequency_window_hours', e.target.value)}
                />
              </label>

              <label>
                <span>窗口上限（条）</span>
                <input
                  type="number"
                  min={1}
                  className="plan-input"
                  value={preferenceForm.max_reminders_per_window}
                  onChange={(e) => handlePreferenceField('max_reminders_per_window', e.target.value)}
                />
              </label>

              <label>
                <span>容忍偏差（分钟）</span>
                <input
                  type="number"
                  min={15}
                  className="plan-input"
                  value={preferenceForm.preferred_tolerance_minutes}
                  onChange={(e) => handlePreferenceField('preferred_tolerance_minutes', e.target.value)}
                />
              </label>
            </div>

            <div className="reminder-channel-row">
              <span>提醒渠道</span>
              {['app', 'email', 'sms'].map((channel) => (
                <label key={channel}>
                  <input
                    type="checkbox"
                    checked={preferenceForm.channels.includes(channel)}
                    onChange={() => toggleChannel(channel)}
                  />
                  {channel}
                </label>
              ))}
            </div>

            <div className="reminder-channel-row">
              <label>
                <input
                  type="checkbox"
                  checked={Boolean(preferenceForm.merge_similar_enabled)}
                  onChange={(e) => handlePreferenceField('merge_similar_enabled', e.target.checked)}
                />
                启用相似提醒合并
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={Boolean(preferenceForm.high_priority_bypass_cap)}
                  onChange={(e) => handlePreferenceField('high_priority_bypass_cap', e.target.checked)}
                />
                高优先级可突破上限
              </label>
              <button className="plan-filter-btn" type="button" onClick={savePreferences} disabled={savingPrefs}>
                {savingPrefs ? '保存中...' : '保存策略'}
              </button>
            </div>

            <div className="reminder-pref-history">
              <h4>配置变更历史</h4>
              {preferenceHistory.map((item) => (
                <div key={item.id} className="reminder-pref-history-item">
                  <div>
                    <strong>{formatPrefSourceLabel(item.source)}</strong>
                    <span className="reminder-subtle"> · {formatDateTime(item.created_at)}</span>
                  </div>
                  <div className="reminder-subtle">
                    频率窗口 {Number(item?.after?.strategy_config?.frequency_window_hours || 0)}h，
                    上限 {Number(item?.after?.strategy_config?.max_reminders_per_window || 0)} 条，
                    渠道 {(Array.isArray(item?.after?.channels) ? item.after.channels : []).join(', ') || '-'}
                  </div>
                  <button
                    className="plan-link-btn"
                    type="button"
                    disabled={rollingBackHistoryId === item.id}
                    onClick={() => rollbackByHistory(item)}
                  >
                    {rollingBackHistoryId === item.id ? '回滚中...' : '回滚到此版本前'}
                  </button>
                </div>
              ))}
              {preferenceHistory.length === 0 && <p className="reminder-empty">暂无配置变更历史</p>}
            </div>
          </div>

          <div className="card">
            <div className="reminder-toolbar">
              <label>
                趋势窗口
                <select
                  value={analyticsDays}
                  onChange={(e) => {
                    const next = Number(e.target.value) || 14;
                    setAnalyticsDays(next);
                    loadData(statusFilter, next, auditActionFilter);
                  }}
                  className="plan-input"
                >
                  <option value={7}>近7天</option>
                  <option value={14}>近14天</option>
                  <option value={30}>近30天</option>
                </select>
              </label>
              {selectedTrendDay && (
                <button
                  className="plan-filter-btn"
                  onClick={() => setSelectedTrendDay('')}
                  type="button"
                >
                  清除日期筛选（{selectedTrendDay}）
                </button>
              )}
            </div>
            <div className="reminder-trend-wrap">
              {(analytics?.trend || []).slice(-14).map((row) => {
                const c = Number(row.created || 0);
                const s = Number(row.sent || 0);
                const f = Number(row.failed || 0);
                const m = Number(row.merged || 0);
                return (
                  <button
                    key={row.day}
                    type="button"
                    className={`reminder-trend-item${selectedTrendDay === row.day ? ' active' : ''}`}
                    title={`${row.day} 创建${c} 发送${s} 失败${f} 合并${m}（点击筛选）`}
                    onClick={() => setSelectedTrendDay((prev) => (prev === row.day ? '' : row.day))}
                  >
                    <div className="reminder-trend-stack">
                      <span className="created" style={{ height: `${(c / maxTrend) * 100}%` }} />
                      <span className="sent" style={{ height: `${(s / maxTrend) * 100}%` }} />
                      <span className="failed" style={{ height: `${(f / maxTrend) * 100}%` }} />
                      <span className="merged" style={{ height: `${(m / maxTrend) * 100}%` }} />
                    </div>
                    <div className="reminder-trend-label">{String(row.day || '').slice(5)}</div>
                  </button>
                );
              })}
            </div>
            {Array.isArray(analytics?.source_counts) && analytics.source_counts.length > 0 && (
              <div className="reminder-source-cloud">
                {analytics.source_counts.slice(0, 10).map((item) => (
                  <span key={item.key} className="reminder-source-chip">{item.key} · {item.count}</span>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="reminder-toolbar">
              <label>
                状态筛选
                <select
                  value={statusFilter}
                  onChange={(e) => {
                    const next = e.target.value;
                    setStatusFilter(next);
                    loadData(next);
                  }}
                  className="plan-input"
                >
                  <option value="all">全部</option>
                  <option value="pending">待发送</option>
                  <option value="sent">已发送</option>
                  <option value="failed">发送失败</option>
                  <option value="merged">已合并</option>
                </select>
              </label>

              <label>
                来源筛选
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="plan-input"
                >
                  <option value="all">全部来源</option>
                  {sourceOptions.map((source) => (
                    <option key={source} value={source}>{source}</option>
                  ))}
                </select>
              </label>

              <button className="plan-filter-btn" onClick={() => loadData(statusFilter)} disabled={loading}>
                {loading ? '刷新中...' : '刷新'}
              </button>
              <button
                className="plan-filter-btn"
                type="button"
                onClick={() => {
                  setStatusFilter('failed');
                  loadData('failed', analyticsDays, auditActionFilter);
                }}
                disabled={loading}
              >
                仅看失败
              </button>
              <button className="plan-filter-btn" type="button" onClick={handleRetryFailed} disabled={batching}>
                重试失败提醒
              </button>
            </div>

            <div className="reminder-batch-bar">
              <label>
                <input type="checkbox" checked={isAllSelected} onChange={toggleAll} />
                {' '}全选当前筛选结果
              </label>
              <span>已选 {selectedIds.length} 条</span>
              <button
                className="plan-filter-btn"
                disabled={selectedIds.length === 0 || batching}
                onClick={() => handleBatchStatus('sent', '批量标记已发送')}
              >
                标记已发送
              </button>
              <button
                className="plan-filter-btn"
                disabled={selectedIds.length === 0 || batching}
                onClick={() => handleBatchStatus('pending', '批量恢复待发送')}
              >
                恢复待发送
              </button>
              <button
                className="plan-filter-btn"
                disabled={selectedIds.length === 0 || batching}
                onClick={handleBatchDelete}
              >
                删除选中
              </button>
            </div>

            {error && <p className="ts-error">{error}</p>}
            {message && <p className="reminder-success">{message}</p>}

            <div className="reminder-table-wrap">
              <table className="reminder-table">
                <thead>
                  <tr>
                    <th />
                    <th>状态</th>
                    <th>标题</th>
                    <th>来源</th>
                    <th>计划时间</th>
                    <th>发送时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <input type="checkbox" checked={selectedIds.includes(row.id)} onChange={() => toggleRow(row.id)} />
                      </td>
                      <td><span className={`reminder-status ${row.status || 'pending'}`}>{formatStatusLabel(row.status)}</span></td>
                      <td>
                        <div className="reminder-title">{row.title}</div>
                        <div className="reminder-subtle">{row.content}</div>
                      </td>
                      <td>{row?.metadata?.source || '-'}</td>
                      <td>{formatDateTime(row.scheduled_at)}</td>
                      <td>{formatDateTime(row.sent_at)}</td>
                      <td>
                        <div className="reminder-actions">
                          <button type="button" className="plan-link-btn" onClick={() => handleSingleStatus(row.id, 'sent')}>发送</button>
                          <button type="button" className="plan-link-btn" onClick={() => handleSingleStatus(row.id, 'pending')}>待发</button>
                          <button type="button" className="plan-link-btn" onClick={() => handleSingleDelete(row.id)}>删除</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filteredRows.length === 0 && (
                    <tr>
                      <td colSpan={7} className="reminder-empty">暂无提醒数据</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <div className="reminder-toolbar">
              <h3 style={{ marginRight: 'auto' }}>操作审计日志</h3>
              <label>
                动作筛选
                <select
                  value={auditActionFilter}
                  onChange={(e) => {
                    const next = e.target.value;
                    setAuditActionFilter(next);
                    loadData(statusFilter, analyticsDays, next);
                  }}
                  className="plan-input"
                >
                  <option value="all">全部</option>
                  <option value="create">创建提醒</option>
                  <option value="status_update">状态更新</option>
                  <option value="batch_status_update">批量状态更新</option>
                  <option value="delete">删除提醒</option>
                  <option value="batch_delete">批量删除</option>
                  <option value="plan_apply_create">计划建议创建</option>
                  <option value="preference_update">偏好配置更新</option>
                  <option value="preference_preset_apply">应用策略预设</option>
                  <option value="preference_rollback">偏好配置回滚</option>
                </select>
              </label>
            </div>
            <div className="reminder-audit-list">
              {auditLogs.map((log) => (
                <div key={log.id} className="reminder-audit-item">
                  <div>
                    <strong>{formatActionLabel(log.action)}</strong> · {formatDateTime(log.created_at)}
                  </div>
                  <div className="reminder-subtle">reminder_id: {log.reminder_id}</div>
                  <div className="reminder-subtle">{JSON.stringify(log.detail || {})}</div>
                </div>
              ))}
              {auditLogs.length === 0 && <p className="reminder-empty">暂无审计日志</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ReminderCenter;
