import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  batchReviewMistakes,
  createMistake,
  exportMistakes,
  getMistakeClusters,
  getDueMistakes,
  getMistakeAnalysis,
  getMistakeReviewQueue,
  getMistakeStats,
  getMistakes,
  importMistakes,
  normalizeUiError,
  reviewMistake,
} from '../utils/api';

import TopNav from "../components/layout/TopNav";
const emptyForm = {
  module: 'writing',
  question_id: '',
  question_type: 'general',
  error_type: 'grammar',
  content: '',
  user_answer: '',
  correct_answer: '',
  explanation: '',
  difficulty: 'medium',
  tags: '',
};

const toDayStartTs = (dateText) => {
  if (!dateText) return null;
  const dt = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(dt.getTime())) return null;
  return Math.floor(dt.getTime() / 1000);
};

const toDayEndTs = (dateText) => {
  if (!dateText) return null;
  const dt = new Date(`${dateText}T23:59:59`);
  if (Number.isNaN(dt.getTime())) return null;
  return Math.floor(dt.getTime() / 1000);
};

const formatDateInput = (ts) => {
  if (!ts) return '';
  const dt = new Date(Number(ts) * 1000);
  if (Number.isNaN(dt.getTime())) return '';
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, '0');
  const d = String(dt.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const dateTextOffset = (offsetDays = 0) => {
  const now = new Date();
  now.setDate(now.getDate() + offsetDays);
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const MISTAKES_QUEUE_SORT_STORAGE_KEY = 'mistakes_queue_sort_by_v1';

function Mistakes() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mistakes, setMistakes] = useState([]);
  const [stats, setStats] = useState({ total: 0, by_module: {} });
  const [analysis, setAnalysis] = useState({
    due_count: 0,
    avg_mastery: 0,
    by_error_type: {},
    by_error_and_question_type: {},
    vocabulary_test_wrong_count: 0,
    vocabulary_test_wrong_ratio: 0,
  });
  const [dueMistakes, setDueMistakes] = useState([]);
  const [reviewQueue, setReviewQueue] = useState([]);
  const [queueSortBy, setQueueSortBy] = useState('priority');
  const [queueKeyword, setQueueKeyword] = useState('');
  const [queuePage, setQueuePage] = useState(1);
  const [queuePageSize, setQueuePageSize] = useState(10);
  const [clusters, setClusters] = useState([]);
  const [moduleFilter, setModuleFilter] = useState('');
  const [questionTypeFilter, setQuestionTypeFilter] = useState('');
  const [errorTypeFilter, setErrorTypeFilter] = useState('');
  const [createdFrom, setCreatedFrom] = useState(null);
  const [createdTo, setCreatedTo] = useState(null);
  const [nextReviewFrom, setNextReviewFrom] = useState(null);
  const [nextReviewTo, setNextReviewTo] = useState(null);
  const [dateFromInput, setDateFromInput] = useState('');
  const [dateToInput, setDateToInput] = useState('');
  const [dueDateFromInput, setDueDateFromInput] = useState('');
  const [dueDateToInput, setDueDateToInput] = useState('');
  const [importText, setImportText] = useState('');
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const sortLabelMap = {
    priority: '优先级',
    gain: '预计增益',
    projected: '复习后掌握度',
  };

  const onQueueSortChange = (nextSort) => {
    if (!nextSort || !sortLabelMap[nextSort]) return;
    setQueueSortBy(nextSort);
    setQueuePage(1);
  };

  const sortedReviewQueue = useMemo(() => {
    const keyword = String(queueKeyword || '').trim().toLowerCase();
    const filteredRows = (reviewQueue || []).filter((item) => {
      if (!keyword) return true;
      const searchText = [
        item?.question_id,
        item?.error_type,
        item?.module,
        item?.question_type,
        item?.content,
      ].map((v) => String(v || '').toLowerCase()).join(' ');
      return searchText.includes(keyword);
    });
    const rows = [...filteredRows];
    const toNum = (v) => Number(v || 0);
    if (queueSortBy === 'gain') {
      rows.sort((a, b) => toNum(b.expected_mastery_gain) - toNum(a.expected_mastery_gain));
      return rows;
    }
    if (queueSortBy === 'projected') {
      rows.sort((a, b) => toNum(b.projected_mastery_after_review) - toNum(a.projected_mastery_after_review));
      return rows;
    }
    rows.sort((a, b) => toNum(b.priority_score) - toNum(a.priority_score));
    return rows;
  }, [reviewQueue, queueSortBy, queueKeyword]);

  const pagedReviewQueue = useMemo(() => {
    const start = (Math.max(1, queuePage) - 1) * queuePageSize;
    return sortedReviewQueue.slice(start, start + queuePageSize);
  }, [sortedReviewQueue, queuePage, queuePageSize]);

  const queueTotalPages = Math.max(1, Math.ceil(sortedReviewQueue.length / queuePageSize));

  useEffect(() => {
    try {
      const stored = localStorage.getItem(MISTAKES_QUEUE_SORT_STORAGE_KEY);
      if (stored === 'priority' || stored === 'gain' || stored === 'projected') {
        setQueueSortBy(stored);
      }
    } catch {
      // ignore localStorage read failures
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(MISTAKES_QUEUE_SORT_STORAGE_KEY, queueSortBy);
    } catch {
      // ignore localStorage write failures
    }
  }, [queueSortBy]);

  useEffect(() => {
    if (queuePage > queueTotalPages) {
      setQueuePage(queueTotalPages);
    }
  }, [queuePage, queueTotalPages]);

  useEffect(() => {
    const params = new URLSearchParams(location.search || '');
    const qModule = params.get('module') || '';
    const qQuestionType = params.get('questionType') || '';
    const qErrorType = params.get('errorType') || '';
    const qDayStart = params.get('dayStart');
    const qDayEnd = params.get('dayEnd');
    const qDueStart = params.get('dueStart');
    const qDueEnd = params.get('dueEnd');
    const qQueueSort = params.get('queueSort');
    const qQueueKeyword = params.get('queueKeyword') || '';
    const qQueuePage = Number(params.get('queuePage') || 1);
    const qQueuePageSize = Number(params.get('queuePageSize') || 10);
    setModuleFilter(qModule);
    setQuestionTypeFilter(qQuestionType);
    setErrorTypeFilter(qErrorType);
    const fromTs = qDayStart ? Number(qDayStart) : null;
    const toTs = qDayEnd ? Number(qDayEnd) : null;
    const dueFromTs = qDueStart ? Number(qDueStart) : null;
    const dueToTs = qDueEnd ? Number(qDueEnd) : null;
    setCreatedFrom(fromTs);
    setCreatedTo(toTs);
    setNextReviewFrom(dueFromTs);
    setNextReviewTo(dueToTs);
    setDateFromInput(formatDateInput(fromTs));
    setDateToInput(formatDateInput(toTs));
    setDueDateFromInput(formatDateInput(dueFromTs));
    setDueDateToInput(formatDateInput(dueToTs));
    if (qQueueSort === 'priority' || qQueueSort === 'gain' || qQueueSort === 'projected') {
      setQueueSortBy(qQueueSort);
    }
    setQueueKeyword(qQueueKeyword);
    if (Number.isFinite(qQueuePage) && qQueuePage >= 1) {
      setQueuePage(Math.floor(qQueuePage));
    } else {
      setQueuePage(1);
    }
    if ([10, 20, 30].includes(qQueuePageSize)) {
      setQueuePageSize(qQueuePageSize);
    } else {
      setQueuePageSize(10);
    }
  }, [location.search]);

  useEffect(() => {
    const next = new URLSearchParams();
    if (moduleFilter) next.set('module', moduleFilter);
    if (questionTypeFilter) next.set('questionType', questionTypeFilter);
    if (errorTypeFilter) next.set('errorType', errorTypeFilter);
    if (createdFrom) next.set('dayStart', String(createdFrom));
    if (createdTo) next.set('dayEnd', String(createdTo));
    if (nextReviewFrom) next.set('dueStart', String(nextReviewFrom));
    if (nextReviewTo) next.set('dueEnd', String(nextReviewTo));
    if (queueSortBy && queueSortBy !== 'priority') next.set('queueSort', queueSortBy);
    if (queueKeyword) next.set('queueKeyword', queueKeyword);
    if (queuePage > 1) next.set('queuePage', String(queuePage));
    if (queuePageSize !== 10) next.set('queuePageSize', String(queuePageSize));
    const nextSearch = next.toString();
    const currentSearch = String(location.search || '').replace(/^\?/, '');
    if (nextSearch === currentSearch) return;
    navigate(`/mistakes${nextSearch ? `?${nextSearch}` : ''}`, { replace: true });
  }, [moduleFilter, questionTypeFilter, errorTypeFilter, createdFrom, createdTo, nextReviewFrom, nextReviewTo, queueSortBy, queueKeyword, queuePage, queuePageSize, navigate, location.search]);

  const loadData = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const [mistakeRows, statRows, dueRows, analysisRows] = await Promise.all([
        getMistakes(
          moduleFilter || null,
          100,
          questionTypeFilter || null,
          errorTypeFilter || null,
          createdFrom,
          createdTo,
          nextReviewFrom,
          nextReviewTo,
        ),
        getMistakeStats(),
        getDueMistakes(moduleFilter || null, 20, questionTypeFilter || null),
        getMistakeAnalysis(),
      ]);
      const [queueRows, clusterRows] = await Promise.all([
        getMistakeReviewQueue(moduleFilter || null, 120, questionTypeFilter || null, nextReviewFrom, nextReviewTo),
        getMistakeClusters(moduleFilter || null, 10, questionTypeFilter || null),
      ]);
      setMistakes(mistakeRows);
      setStats(statRows);
      setDueMistakes(dueRows);
      setAnalysis(analysisRows);
      setReviewQueue(queueRows);
      setClusters(clusterRows);
    } catch (e) {
      setError(normalizeUiError(e, '加载错题数据失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [moduleFilter, questionTypeFilter, errorTypeFilter, createdFrom, createdTo, nextReviewFrom, nextReviewTo]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const payload = {
        ...form,
        tags: form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
      };
      await createMistake(payload);
      setForm(emptyForm);
      await loadData();
    } catch (err) {
      setError(typeof err === 'string' ? err : '创建错题失败');
    }
  };

  const onReview = async (id) => {
    try {
      await reviewMistake(id, 0.2);
      setSuccess('已完成 1 条复习');
      await loadData();
    } catch (err) {
      setError(typeof err === 'string' ? err : '复习标记失败');
    }
  };

  const onBatchReviewTop = async () => {
    const ids = sortedReviewQueue.slice(0, 8).map((x) => x.id).filter(Boolean);
    if (ids.length === 0) return;
    try {
      setError('');
      const result = await batchReviewMistakes(ids, 0.2);
      setSuccess(`批量复习完成：${result.reviewed}/${result.requested}`);
      await loadData();
    } catch (err) {
      setError(typeof err === 'string' ? err : '批量复习失败');
    }
  };

  const routeByMistake = (item) => {
    const qType = String(item?.question_type || '').toLowerCase();
    const module = String(item?.module || '').toLowerCase();
    if (qType === 'vocabulary_test') return '/vocabulary';
    if (qType === 'listening_quiz' || module === 'listening') return '/listening';
    if (qType === 'reading_quiz' || module === 'reading') return '/reading';
    if (qType === 'speaking_assessment' || module === 'speaking') return '/speaking';
    if (qType === 'writing_task1' || module === 'writing') return '/writing';
    return '/mistakes';
  };

  const onReplay = (item) => {
    const params = new URLSearchParams({
      from: 'mistakes',
      replay: '1',
      mistakeId: String(item.id || ''),
      questionId: String(item.question_id || ''),
      questionType: String(item.question_type || ''),
      module: String(item.module || ''),
    });
    navigate(`${routeByMistake(item)}?${params.toString()}`);
  };

  const applyDateFilter = () => {
    setCreatedFrom(toDayStartTs(dateFromInput));
    setCreatedTo(toDayEndTs(dateToInput));
  };

  const clearDateFilter = () => {
    setDateFromInput('');
    setDateToInput('');
    setCreatedFrom(null);
    setCreatedTo(null);
  };

  const applyDueDateFilter = () => {
    setNextReviewFrom(toDayStartTs(dueDateFromInput));
    setNextReviewTo(toDayEndTs(dueDateToInput));
  };

  const clearDueDateFilter = () => {
    setDueDateFromInput('');
    setDueDateToInput('');
    setNextReviewFrom(null);
    setNextReviewTo(null);
  };

  const applyPreset = (preset) => {
    if (preset === 'today') {
      const today = dateTextOffset(0);
      setDateFromInput(today);
      setDateToInput(today);
      setCreatedFrom(toDayStartTs(today));
      setCreatedTo(toDayEndTs(today));
      return;
    }
    if (preset === 'last7') {
      const from = dateTextOffset(-6);
      const to = dateTextOffset(0);
      setDateFromInput(from);
      setDateToInput(to);
      setCreatedFrom(toDayStartTs(from));
      setCreatedTo(toDayEndTs(to));
      return;
    }
    if (preset === 'listening_week') {
      const from = dateTextOffset(-6);
      const to = dateTextOffset(0);
      setModuleFilter('listening');
      setQuestionTypeFilter('listening_quiz');
      setDateFromInput(from);
      setDateToInput(to);
      setCreatedFrom(toDayStartTs(from));
      setCreatedTo(toDayEndTs(to));
      return;
    }
    if (preset === 'reading_week') {
      const from = dateTextOffset(-6);
      const to = dateTextOffset(0);
      setModuleFilter('reading');
      setQuestionTypeFilter('reading_quiz');
      setDateFromInput(from);
      setDateToInput(to);
      setCreatedFrom(toDayStartTs(from));
      setCreatedTo(toDayEndTs(to));
      return;
    }
    if (preset === 'clear') {
      setModuleFilter('');
      setQuestionTypeFilter('');
      setErrorTypeFilter('');
      clearDateFilter();
      clearDueDateFilter();
      return;
    }
    if (preset === 'due_today') {
      const today = dateTextOffset(0);
      setDueDateFromInput(today);
      setDueDateToInput(today);
      setNextReviewFrom(toDayStartTs(today));
      setNextReviewTo(toDayEndTs(today));
      return;
    }
    if (preset === 'due_last7') {
      const from = dateTextOffset(-6);
      const to = dateTextOffset(0);
      setDueDateFromInput(from);
      setDueDateToInput(to);
      setNextReviewFrom(toDayStartTs(from));
      setNextReviewTo(toDayEndTs(to));
    }
  };

  const downloadTextFile = (content, filename, type = 'text/plain') => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const onExportJson = async () => {
    try {
      const data = await exportMistakes('json', moduleFilter || null, 1000, questionTypeFilter || null, errorTypeFilter || null);
      downloadTextFile(JSON.stringify(data, null, 2), 'mistakes_export.json', 'application/json');
    } catch (err) {
      setError(typeof err === 'string' ? err : '导出 JSON 失败');
    }
  };

  const onExportCsv = async () => {
    try {
      const data = await exportMistakes('csv', moduleFilter || null, 1000, questionTypeFilter || null, errorTypeFilter || null);
      downloadTextFile(data, 'mistakes_export.csv', 'text/csv');
    } catch (err) {
      setError(typeof err === 'string' ? err : '导出 CSV 失败');
    }
  };

  const onImport = async () => {
    try {
      const parsed = JSON.parse(importText || '[]');
      const items = Array.isArray(parsed) ? parsed : (parsed.items || []);
      await importMistakes(items);
      setImportText('');
      await loadData();
    } catch (err) {
      setError(typeof err === 'string' ? err : '导入失败，请检查 JSON 格式');
    }
  };

  return (
    <div className="home-page web-dashboard mistakes-page">
      <TopNav />

      <div className="content-area content-shell">
        <div className="web-page-head">
          <div>
            <h2>错题本</h2>
            <p>错题筛选、复习队列与练习回流在这里集中处理。</p>
          </div>
          <div className="web-page-head-actions">
            <button onClick={loadData}>刷新列表</button>
          </div>
        </div>
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>统计</h3>
          <p>错题总数：{stats.total || 0}</p>
          <p>模块分布：{Object.entries(stats.by_module || {}).map(([k, v]) => `${k}:${v}`).join(' | ') || '暂无'}</p>
          <p>到期复习：{analysis.due_count || 0}</p>
          <p>平均掌握度：{Math.round((analysis.avg_mastery || 0) * 100)}%</p>
          <p>错因分布：{Object.entries(analysis.by_error_type || {}).map(([k, v]) => `${k}:${v}`).join(' | ') || '暂无'}</p>
          <p>
            词汇测试错题：{analysis.vocabulary_test_wrong_count || 0}
            {' '}（占比 {Math.round((analysis.vocabulary_test_wrong_ratio || 0) * 100)}%）
          </p>
          <p>
            组合分布（error|question_type）：
            {Object.entries(analysis.by_error_and_question_type || {}).map(([k, v]) => `${k}:${v}`).join(' | ') || '暂无'}
          </p>
          {(createdFrom || createdTo) && (
            <p style={{ color: '#4A6CF7' }}>
              当前按日期筛选：{createdFrom ? new Date(createdFrom * 1000).toLocaleDateString() : '-'}
              {' '}~{' '}
              {createdTo ? new Date(createdTo * 1000).toLocaleDateString() : '-'}
            </p>
          )}
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>今日优先复习队列</h3>
          <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
            <button onClick={onBatchReviewTop} disabled={sortedReviewQueue.length === 0}>一键复习 Top8</button>
            <span style={{ color: '#666', fontSize: 13 }}>
              当前排序：{sortLabelMap[queueSortBy] || '优先级'}（可点击表头切换）
            </span>
            <input
              value={queueKeyword}
              onChange={(e) => {
                setQueueKeyword(e.target.value);
                setQueuePage(1);
              }}
              placeholder="搜索题目ID/错因/模块"
              style={{ minWidth: 220 }}
            />
            <label>每页：</label>
            <select
              value={queuePageSize}
              onChange={(e) => {
                setQueuePageSize(Number(e.target.value) || 10);
                setQueuePage(1);
              }}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={30}>30</option>
            </select>
          </div>
          {pagedReviewQueue.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th align="left">模块</th>
                  <th align="left">题目ID</th>
                  <th align="left">错因</th>
                  <th
                    align="left"
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => onQueueSortChange('priority')}
                    title="点击按优先级排序"
                  >
                    优先级{queueSortBy === 'priority' ? ' ↓' : ''}
                  </th>
                  <th
                    align="left"
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => onQueueSortChange('gain')}
                    title="点击按预计增益排序"
                  >
                    预计增益{queueSortBy === 'gain' ? ' ↓' : ''}
                  </th>
                  <th
                    align="left"
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => onQueueSortChange('projected')}
                    title="点击按复习后掌握度排序"
                  >
                    复习后掌握度{queueSortBy === 'projected' ? ' ↓' : ''}
                  </th>
                  <th align="left">原因</th>
                  <th align="left">操作</th>
                </tr>
              </thead>
              <tbody>
                {pagedReviewQueue.map((item) => (
                  <tr key={item.id}>
                    <td>{item.module}</td>
                    <td>{item.question_id}</td>
                    <td>{item.error_type}</td>
                    <td>{Number(item.priority_score || 0).toFixed(3)}</td>
                    <td>{Math.round((Number(item.expected_mastery_gain || 0)) * 100)}%</td>
                    <td>{Math.round((Number(item.projected_mastery_after_review || 0)) * 100)}%</td>
                    <td>{item.priority_reason}</td>
                    <td>
                      <button onClick={() => onReplay(item)}>一键重练</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>暂无优先复习项</p>
          )}
          {sortedReviewQueue.length > 0 && (
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
              <button onClick={() => setQueuePage((p) => Math.max(1, p - 1))} disabled={queuePage <= 1}>
                上一页
              </button>
              <span>
                第 {queuePage}/{queueTotalPages} 页 · 共 {sortedReviewQueue.length} 条
              </span>
              <button
                onClick={() => setQueuePage((p) => Math.min(queueTotalPages, p + 1))}
                disabled={queuePage >= queueTotalPages}
              >
                下一页
              </button>
            </div>
          )}
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>错因聚类（Top10）</h3>
          {clusters.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th align="left">模块</th>
                  <th align="left">题型</th>
                  <th align="left">错因</th>
                  <th align="left">数量</th>
                  <th align="left">到期</th>
                  <th align="left">平均掌握度</th>
                  <th align="left">风险分</th>
                </tr>
              </thead>
              <tbody>
                {clusters.map((item, idx) => (
                  <tr key={`${item.module}_${item.question_type}_${item.error_type}_${idx}`}>
                    <td>{item.module}</td>
                    <td>{item.question_type}</td>
                    <td>{item.error_type}</td>
                    <td>{item.count}</td>
                    <td>{item.due_count}</td>
                    <td>{Math.round((item.avg_mastery || 0) * 100)}%</td>
                    <td>{Number(item.risk_score || 0).toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p>暂无聚类数据</p>}
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>新增错题</h3>
          <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8 }}>
            <input placeholder="question_id" value={form.question_id} onChange={(e) => setForm({ ...form, question_id: e.target.value })} required />
            <select value={form.module} onChange={(e) => setForm({ ...form, module: e.target.value })}>
              <option value="writing">writing</option>
              <option value="speaking">speaking</option>
              <option value="reading">reading</option>
              <option value="listening">listening</option>
            </select>
            <input placeholder="错误类型，如 grammar" value={form.error_type} onChange={(e) => setForm({ ...form, error_type: e.target.value })} />
            <input placeholder="用户答案" value={form.user_answer} onChange={(e) => setForm({ ...form, user_answer: e.target.value })} />
            <input placeholder="正确答案" value={form.correct_answer} onChange={(e) => setForm({ ...form, correct_answer: e.target.value })} />
            <textarea placeholder="题目内容/错因说明" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} />
            <input placeholder="tags 逗号分隔" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
            <button type="submit">保存错题</button>
          </form>
        </div>

        <div className="card">
          <h3>错题列表</h3>
          <div style={{ marginBottom: 12 }}>
            <label>模块筛选：</label>
            <select value={moduleFilter} onChange={(e) => setModuleFilter(e.target.value)}>
              <option value="">全部</option>
              <option value="writing">writing</option>
              <option value="speaking">speaking</option>
              <option value="reading">reading</option>
              <option value="listening">listening</option>
            </select>
            <label style={{ marginLeft: 12 }}>题型筛选：</label>
            <select value={questionTypeFilter} onChange={(e) => setQuestionTypeFilter(e.target.value)}>
              <option value="">全部</option>
              <option value="diagnostic">diagnostic</option>
              <option value="vocabulary_test">vocabulary_test</option>
              <option value="listening_quiz">listening_quiz</option>
              <option value="reading_quiz">reading_quiz</option>
              <option value="speaking_assessment">speaking_assessment</option>
              <option value="writing_task1">writing_task1</option>
              <option value="manual">manual</option>
              <option value="general">general</option>
            </select>
            <label style={{ marginLeft: 12 }}>错因筛选：</label>
            <input
              value={errorTypeFilter}
              onChange={(e) => setErrorTypeFilter(e.target.value)}
              placeholder="如 reading_inference_error"
              style={{ marginLeft: 6, width: 220 }}
            />
            <button
              onClick={() => setQuestionTypeFilter('vocabulary_test')}
              style={{ marginLeft: 8 }}
            >
              仅看词汇测试错题
            </button>
            <button
              onClick={() => {
                setModuleFilter('listening');
                setQuestionTypeFilter('listening_quiz');
              }}
              style={{ marginLeft: 8 }}
            >
              仅看听力测验错题
            </button>
            <button
              onClick={() => {
                setModuleFilter('reading');
                setQuestionTypeFilter('reading_quiz');
              }}
              style={{ marginLeft: 8 }}
            >
              仅看阅读测验错题
            </button>
            <button
              onClick={() => {
                setModuleFilter('speaking');
                setQuestionTypeFilter('speaking_assessment');
              }}
              style={{ marginLeft: 8 }}
            >
              仅看口语评估弱项
            </button>
            <button
              onClick={() => {
                setModuleFilter('writing');
                setQuestionTypeFilter('writing_task1');
              }}
              style={{ marginLeft: 8 }}
            >
              仅看写作Task1弱项
            </button>
            <button onClick={() => applyPreset('today')} style={{ marginLeft: 8 }}>今日新增</button>
            <button onClick={() => applyPreset('last7')} style={{ marginLeft: 8 }}>近7天新增</button>
            <button onClick={() => applyPreset('listening_week')} style={{ marginLeft: 8 }}>本周听力错题</button>
            <button onClick={() => applyPreset('reading_week')} style={{ marginLeft: 8 }}>本周阅读错题</button>
            <button onClick={() => applyPreset('due_today')} style={{ marginLeft: 8 }}>今日到期</button>
            <button onClick={() => applyPreset('due_last7')} style={{ marginLeft: 8 }}>近7天到期</button>
            <button onClick={() => applyPreset('clear')} style={{ marginLeft: 8 }}>清空全部筛选</button>
            <label style={{ marginLeft: 12 }}>起始日期：</label>
            <input
              type="date"
              value={dateFromInput}
              onChange={(e) => setDateFromInput(e.target.value)}
              style={{ marginLeft: 6 }}
            />
            <label style={{ marginLeft: 12 }}>结束日期：</label>
            <input
              type="date"
              value={dateToInput}
              onChange={(e) => setDateToInput(e.target.value)}
              style={{ marginLeft: 6 }}
            />
            <button onClick={applyDateFilter} style={{ marginLeft: 8 }}>应用日期</button>
            <button onClick={clearDateFilter} style={{ marginLeft: 8 }}>清空日期</button>
            <label style={{ marginLeft: 12 }}>到期起始：</label>
            <input
              type="date"
              value={dueDateFromInput}
              onChange={(e) => setDueDateFromInput(e.target.value)}
              style={{ marginLeft: 6 }}
            />
            <label style={{ marginLeft: 12 }}>到期结束：</label>
            <input
              type="date"
              value={dueDateToInput}
              onChange={(e) => setDueDateToInput(e.target.value)}
              style={{ marginLeft: 6 }}
            />
            <button onClick={applyDueDateFilter} style={{ marginLeft: 8 }}>应用到期</button>
            <button onClick={clearDueDateFilter} style={{ marginLeft: 8 }}>清空到期</button>
            <button onClick={loadData} style={{ marginLeft: 8 }}>刷新</button>
            <button onClick={onExportJson} style={{ marginLeft: 8 }}>导出JSON</button>
            <button onClick={onExportCsv} style={{ marginLeft: 8 }}>导出CSV</button>
          </div>
          <div style={{ marginBottom: 12 }}>
            <h4 style={{ marginBottom: 6 }}>导入错题（JSON）</h4>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='粘贴数组或 { "items": [...] }'
              style={{ width: '100%', minHeight: 90 }}
            />
            <button onClick={onImport} style={{ marginTop: 8 }}>导入</button>
          </div>
          <div style={{ marginBottom: 12 }}>
            <h4 style={{ marginBottom: 6 }}>到期复习（前20）</h4>
            <p>{dueMistakes.map((m) => `${m.question_id}(${m.error_type})`).join(' | ') || '暂无到期项'}</p>
          </div>

          {loading ? <p>加载中...</p> : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th align="left">模块</th>
                  <th align="left">题目ID</th>
                  <th align="left">错误类型</th>
                  <th align="left">掌握度</th>
                  <th align="left">操作</th>
                </tr>
              </thead>
              <tbody>
                {mistakes.map((item) => (
                  <tr key={item.id}>
                    <td>{item.module}</td>
                    <td>{item.question_id}</td>
                    <td>{item.error_type}</td>
                    <td>{Math.round((item.mastery_level || 0) * 100)}%</td>
                    <td>
                      <button onClick={() => onReview(item.id)}>标记已复习</button>
                    </td>
                  </tr>
                ))}
                {mistakes.length === 0 && (
                  <tr><td colSpan={5}>暂无错题</td></tr>
                )}
              </tbody>
            </table>
          )}
          {error && <p style={{ color: 'red' }}>{error}</p>}
          {success && <p style={{ color: 'green' }}>{success}</p>}
        </div>
      </div>
    </div>
  );
}

export default Mistakes;
