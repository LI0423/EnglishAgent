import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  completeDiagnostic,
  getDiagnosticBankHealth,
  getDiagnosticBankVersion,
  getDiagnosticHistorySummary,
  generatePlan7d,
  getDiagnosticReport,
  reloadDiagnosticBank,
  startDiagnostic,
  submitDiagnosticAnswers,
} from '../utils/api';

function Diagnostic() {
  const navItems = [
    { to: '/', label: '🏠 首页' },
    { to: '/chat', label: '🤖 智能对话' },
    { to: '/listening', label: '🎧 听力练习' },
    { to: '/reading', label: '📚 阅读练习' },
    { to: '/writing', label: '📝 写作练习' },
    { to: '/speaking', label: '💬 口语练习' },
    { to: '/mock-exam', label: '🎯 诊断测评' },
    { to: '/reports', label: '📊 学习报告' },
  ];

  const [sessionId, setSessionId] = useState('');
  const [bankVersion, setBankVersion] = useState('');
  const [bankInfo, setBankInfo] = useState(null);
  const [selectedModules, setSelectedModules] = useState(['listening', 'reading', 'writing', 'speaking']);
  const [nextQuestion, setNextQuestion] = useState(null);
  const [answerInput, setAnswerInput] = useState('');
  const [estimatedAbility, setEstimatedAbility] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [report, setReport] = useState(null);
  const [historySummary, setHistorySummary] = useState(null);
  const [planDraft, setPlanDraft] = useState(null);
  const [error, setError] = useState('');

  const onToggleModule = (module) => {
    setSelectedModules((prev) => {
      if (prev.includes(module)) {
        return prev.filter((m) => m !== module);
      }
      return [...prev, module];
    });
  };

  const fetchNext = async (sid) => {
    const res = await submitDiagnosticAnswers(sid, []);
    setNextQuestion(res.next_question || null);
    setEstimatedAbility(res.estimated_ability || null);
    setLastResult(res.last_result || null);
  };

  const loadHistorySummary = async () => {
    try {
      const data = await getDiagnosticHistorySummary(10);
      setHistorySummary(data);
    } catch {
      setHistorySummary(null);
    }
  };

  const loadBankInfo = async () => {
    try {
      const [version, health] = await Promise.all([
        getDiagnosticBankVersion(),
        getDiagnosticBankHealth(),
      ]);
      setBankInfo({ version, health });
    } catch {
      setBankInfo(null);
    }
  };

  useEffect(() => {
    loadHistorySummary();
    loadBankInfo();
  }, []);

  return (
    <div className="home-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>🎯 诊断测评</h1></div>
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
            <h3>开始诊断</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              {['listening', 'reading', 'writing', 'speaking'].map((m) => (
                <label key={m}>
                  <input
                    type="checkbox"
                    checked={selectedModules.includes(m)}
                    onChange={() => onToggleModule(m)}
                  />
                  {m}
                </label>
              ))}
            </div>
            <button
              onClick={async () => {
                setError('');
                setReport(null);
                try {
                  const res = await startDiagnostic(selectedModules);
                  setSessionId(res.id);
                  setBankVersion(res.bank_version || '');
                  setNextQuestion(res.next_question || null);
                  setEstimatedAbility(null);
                  setLastResult(null);
                  setPlanDraft(null);
                } catch (e) {
                  setError(typeof e === 'string' ? e : '开始失败');
                }
              }}
            >
              开始测评
            </button>
            <p style={{ marginTop: 8 }}>session_id: {sessionId || '未开始'}</p>
            {bankVersion && <p>题库版本: {bankVersion}</p>}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>题库治理</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
              <button onClick={loadBankInfo}>刷新题库状态</button>
              <button
                onClick={async () => {
                  setError('');
                  try {
                    const health = await reloadDiagnosticBank();
                    setBankInfo((prev) => ({ version: prev?.version || null, health }));
                    setBankVersion(health?.version || '');
                  } catch (e) {
                    setError(typeof e === 'string' ? e : '重载题库失败');
                  }
                }}
              >
                重载题库
              </button>
            </div>
            {bankInfo ? (
              <div style={{ fontSize: 14 }}>
                <p>版本：{bankInfo.health?.version || bankInfo.version?.version || '-'}</p>
                <p>来源：{bankInfo.health?.source || bankInfo.version?.source || '-'}</p>
                <p>总题量：{bankInfo.health?.total_questions ?? '-'}</p>
                <p>fallback：{String(bankInfo.health?.has_fallback ?? false)}</p>
              </div>
            ) : (
              <p>暂无题库信息</p>
            )}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>当前题目</h3>
            {nextQuestion ? (
              <div>
                <p>QID: {nextQuestion.question_id}</p>
                <p>{nextQuestion.question}</p>
                {(nextQuestion.options || []).length > 0 && (
                  <div style={{ display: 'grid', gap: 6 }}>
                    {nextQuestion.options.map((opt) => (
                      <button key={opt} onClick={() => setAnswerInput(opt)}>{opt}</button>
                    ))}
                  </div>
                )}
                <input
                  style={{ width: '100%', marginTop: 8 }}
                  value={answerInput}
                  onChange={(e) => setAnswerInput(e.target.value)}
                  placeholder="输入答案（或点选上方选项）"
                />
                <button
                  style={{ marginTop: 8 }}
                  disabled={!sessionId || !nextQuestion.question_id || !answerInput.trim()}
                  onClick={async () => {
                    setError('');
                    try {
                      const res = await submitDiagnosticAnswers(sessionId, [{
                        question_id: nextQuestion.question_id,
                        answer: answerInput.trim(),
                      }]);
                      setEstimatedAbility(res.estimated_ability || null);
                      setNextQuestion(res.next_question || null);
                      setLastResult(res.last_result || null);
                      setAnswerInput('');
                    } catch (e) {
                      setError(typeof e === 'string' ? e : '提交失败');
                    }
                  }}
                >
                  提交答案
                </button>
              </div>
            ) : (
              <p>暂无题目，可点击“开始测评”或“拉取下一题”。</p>
            )}
            <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
              <button disabled={!sessionId} onClick={async () => fetchNext(sessionId)}>拉取下一题</button>
              <button
                disabled={!sessionId}
                onClick={async () => {
                  setError('');
                  try {
                    await completeDiagnostic(sessionId);
                    const rp = await getDiagnosticReport(sessionId);
                    setReport(rp);
                    await loadHistorySummary();
                    setPlanDraft(null);
                  } catch (e) {
                    setError(typeof e === 'string' ? e : '完成失败');
                  }
                }}
              >
                完成并生成报告
              </button>
            </div>
            {estimatedAbility !== null && <p style={{ marginTop: 8 }}>当前能力预估: {estimatedAbility}</p>}
            {lastResult && (
              <div style={{ marginTop: 12, padding: 10, border: '1px solid #ddd', borderRadius: 8 }}>
                <p>上一题结果：{lastResult.is_correct ? '正确' : '错误'}</p>
                <p>模块/难度：{lastResult.module} / {lastResult.difficulty}</p>
                <p>期望答案：{lastResult.expected_answer || '-'}</p>
                <p>解释：{lastResult.explanation}</p>
                {!lastResult.is_correct && (
                  <p>错因标签：{(lastResult.error_tags || []).join(', ') || 'accuracy_issue'}</p>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <h3>诊断报告</h3>
            {report ? (
              <div>
                <p>overall_band: {report.overall_band}</p>
                <h4>module_scores</h4>
                <ul>{(report.module_scores || []).map((s) => <li key={s.module}>{s.module}: {s.score}</li>)}</ul>
                <h4>weaknesses</h4>
                <ul>{(report.weaknesses || []).map((w, idx) => <li key={idx}>{w.module}: {(w.error_types || []).join(', ')}</li>)}</ul>
                <h4>recommendations</h4>
                <ul>{(report.recommendations || []).map((r, idx) => <li key={idx}>{r.content}</li>)}</ul>
                <button
                  onClick={async () => {
                    setError('');
                    try {
                      const weaknesses = (report.weaknesses || []).map((w) => {
                        const base = w.module || 'general';
                        const err = (w.error_types || [])[0];
                        return err ? `${base}_${err}` : base;
                      });
                      const plan = await generatePlan7d(weaknesses, 7.0, '1-2 hours');
                      setPlanDraft(plan);
                    } catch (e) {
                      setError(typeof e === 'string' ? e : '生成计划失败');
                    }
                  }}
                >
                  基于诊断一键生成7天计划
                </button>
              </div>
            ) : <p>暂无报告</p>}
            {planDraft && (
              <div style={{ marginTop: 12 }}>
                <h4>7天计划草案</h4>
                <p>{planDraft.summary}</p>
                <ul>
                  {(planDraft.plan || []).map((day) => (
                    <li key={day.day}>{day.day} - {day.focus_area}</li>
                  ))}
                </ul>
              </div>
            )}
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3>历史对比</h3>
            <button onClick={loadHistorySummary}>刷新历史趋势</button>
            {historySummary ? (
              <div style={{ marginTop: 8 }}>
                <p>测评总次数：{historySummary.total_reports || 0}</p>
                <p>趋势：{historySummary.trend || 'insufficient_data'}</p>
                <p>
                  最近两次总分变化：
                  {historySummary.delta_overall_band === null || historySummary.delta_overall_band === undefined
                    ? '数据不足'
                    : historySummary.delta_overall_band > 0
                      ? `+${historySummary.delta_overall_band}`
                      : `${historySummary.delta_overall_band}`}
                </p>
                <p>
                  最近分数：{historySummary.latest_overall_band ?? '-'}，上一次：{historySummary.previous_overall_band ?? '-'}
                </p>
                <h4>历史记录</h4>
                <ul>
                  {(historySummary.history || []).map((h) => (
                    <li key={h.report_id}>
                      {new Date((h.generated_at || 0) * 1000).toLocaleString()} - overall {h.overall_band}
                    </li>
                  ))}
                  {(historySummary.history || []).length === 0 && <li>暂无历史诊断报告</li>}
                </ul>
              </div>
            ) : (
              <p style={{ marginTop: 8 }}>暂无历史数据，点击刷新加载。</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Diagnostic;
