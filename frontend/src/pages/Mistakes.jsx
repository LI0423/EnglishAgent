import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  createMistake,
  exportMistakes,
  getDueMistakes,
  getMistakeAnalysis,
  getMistakeStats,
  getMistakes,
  importMistakes,
  reviewMistake,
} from '../utils/api';

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

function Mistakes() {
  const location = useLocation();
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
  const [moduleFilter, setModuleFilter] = useState('');
  const [questionTypeFilter, setQuestionTypeFilter] = useState('');
  const [importText, setImportText] = useState('');
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(location.search || '');
    const qModule = params.get('module') || '';
    const qQuestionType = params.get('questionType') || '';
    if (qModule) setModuleFilter(qModule);
    if (qQuestionType) setQuestionTypeFilter(qQuestionType);
  }, [location.search]);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [mistakeRows, statRows, dueRows, analysisRows] = await Promise.all([
        getMistakes(moduleFilter || null, 100, questionTypeFilter || null),
        getMistakeStats(),
        getDueMistakes(moduleFilter || null, 20, questionTypeFilter || null),
        getMistakeAnalysis(),
      ]);
      setMistakes(mistakeRows);
      setStats(statRows);
      setDueMistakes(dueRows);
      setAnalysis(analysisRows);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [moduleFilter, questionTypeFilter]);

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
      await loadData();
    } catch (err) {
      setError(typeof err === 'string' ? err : '复习标记失败');
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
      const data = await exportMistakes('json', moduleFilter || null, 1000, questionTypeFilter || null);
      downloadTextFile(JSON.stringify(data, null, 2), 'mistakes_export.json', 'application/json');
    } catch (err) {
      setError(typeof err === 'string' ? err : '导出 JSON 失败');
    }
  };

  const onExportCsv = async () => {
    try {
      const data = await exportMistakes('csv', moduleFilter || null, 1000, questionTypeFilter || null);
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
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>🔖 错题管理</h1></div>
        </div>
      </header>

      <div className="content-area content-shell">
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
        </div>
      </div>
    </div>
  );
}

export default Mistakes;
