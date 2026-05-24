import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  addVocabularyWord,
  createMistake,
  createSpeakingSession,
  finishSpeakingSession,
  listSpeakingSessions,
  scoreSpeaking,
  startSpeakingPart,
  submitSpeakingTurn,
  summarizeSpeakingSession,
} from '../utils/api';
import { MetricCard, MetricGrid, PageSection, ToolbarRow } from '../components/layout/DesktopUI';
import SidebarMenu from '../components/layout/SidebarMenu';

import TopNav from "../components/layout/TopNav";
const API_BASE = String(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');

function Speaking() {
  const navigate = useNavigate();
  const location = useLocation();

  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState('');
  const [currentMode, setCurrentMode] = useState('coach');
  const [parts, setParts] = useState([]);
  const [partIndex, setPartIndex] = useState(1);
  const [turnText, setTurnText] = useState('');
  const [turnRecords, setTurnRecords] = useState([]);
  const [partPrepTotal, setPartPrepTotal] = useState(0);
  const [partPrepRemaining, setPartPrepRemaining] = useState(0);
  const [partTargetSeconds, setPartTargetSeconds] = useState(45);
  const [answerElapsed, setAnswerElapsed] = useState(0);
  const [turnStartedAt, setTurnStartedAt] = useState(0);
  const [promptAudioUrl, setPromptAudioUrl] = useState('');
  const [voiceConfig, setVoiceConfig] = useState({ withAudio: true, voice: 'F1', lang: 'en' });
  const [transcriptId, setTranscriptId] = useState('');
  const [scoreResult, setScoreResult] = useState(null);
  const [summary, setSummary] = useState(null);
  const [savingSummary, setSavingSummary] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [replayNotice, setReplayNotice] = useState('');
  const [error, setError] = useState('');

  const currentPartPrompt = useMemo(() => {
    const part = (parts || []).find((p) => Number(p.index) === Number(partIndex));
    return part?.prompt || '';
  }, [parts, partIndex]);

  const loadSessions = async () => {
    try {
      setSessions(await listSpeakingSessions(30, 0));
    } catch (e) {
      setError(typeof e === 'string' ? e : '加载会话失败');
    }
  };

  const toAudioSrc = (url) => {
    const raw = String(url || '').trim();
    if (!raw) return '';
    if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
    if (raw.startsWith('/')) return `${API_BASE}${raw}`;
    return `${API_BASE}/${raw}`;
  };

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (!currentSessionId || !turnStartedAt) return undefined;
    const timer = window.setInterval(() => {
      const elapsed = Math.max(0, Math.floor((Date.now() - turnStartedAt) / 1000));
      const prepRemain = Math.max(0, partPrepTotal - elapsed);
      setPartPrepRemaining(prepRemain);
      setAnswerElapsed(prepRemain > 0 ? 0 : (elapsed - partPrepTotal));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [currentSessionId, turnStartedAt, partPrepTotal]);

  useEffect(() => {
    const params = new URLSearchParams(location.search || '');
    if (params.get('replay') !== '1') return;
    const questionId = params.get('questionId') || '';
    setReplayNotice(questionId ? `来自错题重练：题目 ${questionId}` : '来自错题重练：建议先创建口语对练会话');
  }, [location.search]);

  const onCreateSession = async () => {
    setError('');
    setStatusMessage('');
    setTurnRecords([]);
    setSummary(null);
    const s = await createSpeakingSession();
    setCurrentSessionId(s.sessionId);
    setParts(s.parts || []);
    setPartIndex(1);
    setTranscriptId('');
    await loadSessions();
    const partMeta = await startSpeakingPart(s.sessionId, 1, voiceConfig);
    const prep = Number(partMeta?.prepSeconds || 0);
    const target = Number(partMeta?.targetAnswerSeconds || 45);
    setPromptAudioUrl(toAudioSrc(partMeta?.promptAudioUrl));
    setPartPrepTotal(prep);
    setPartPrepRemaining(prep);
    setPartTargetSeconds(target);
    setAnswerElapsed(0);
    setTurnStartedAt(Date.now());
    setStatusMessage('已创建会话并开始 Part 1');
  };

  const onSwitchPart = async (nextPart) => {
    if (!currentSessionId) return;
    setError('');
    const partMeta = await startSpeakingPart(currentSessionId, nextPart, voiceConfig);
    setPartIndex(nextPart);
    const prep = Number(partMeta?.prepSeconds || 0);
    const target = Number(partMeta?.targetAnswerSeconds || 45);
    setPromptAudioUrl(toAudioSrc(partMeta?.promptAudioUrl));
    setPartPrepTotal(prep);
    setPartPrepRemaining(prep);
    setPartTargetSeconds(target);
    setAnswerElapsed(0);
    setTurnStartedAt(Date.now());
    setStatusMessage(`已切换到 Part ${nextPart}`);
  };

  const onSubmitTurn = async () => {
    if (!currentSessionId || !turnText.trim()) return;
    setError('');
    try {
      const res = await submitSpeakingTurn(
        currentSessionId,
        turnText.trim(),
        {
          mode: currentMode,
          partIndex,
          spentSeconds: Math.max(1, answerElapsed),
          withAudio: voiceConfig.withAudio,
          voice: voiceConfig.voice,
          lang: voiceConfig.lang,
        },
      );
      setTurnRecords((prev) => [
        ...prev,
        {
          partIndex: res.partIndex,
          turnIndex: res.turnIndex,
          userText: turnText.trim(),
          examinerPrompt: res.examinerPrompt,
          followUpQuestion: res.followUpQuestion,
          feedback: res.feedback || {},
          shouldMoveNextPart: Boolean(res.shouldMoveNextPart),
          spentSeconds: Number(res.spentSeconds || 0),
          targetSeconds: Number(res.targetSeconds || 45),
          pacingFeedback: res.pacingFeedback || '',
          examinerPromptAudioUrl: toAudioSrc(res.examinerPromptAudioUrl),
          followUpAudioUrl: toAudioSrc(res.followUpAudioUrl),
        },
      ]);
      setTurnText('');
      setTurnStartedAt(Date.now());
      setPartPrepTotal(0);
      setPartPrepRemaining(0);
      setAnswerElapsed(0);
      if (res.shouldMoveNextPart && partIndex < 3) {
        await onSwitchPart(partIndex + 1);
      } else if (res.shouldMoveNextPart && partIndex === 3) {
        setStatusMessage('Part 3 已达到建议轮次，可以结束会话并生成复盘。');
      }
    } catch (e) {
      setError(typeof e === 'string' ? e : '提交回合失败');
    }
  };

  const onFinishAndReview = async () => {
    if (!currentSessionId) return;
    setError('');
    try {
      const finished = await finishSpeakingSession(currentSessionId);
      setTranscriptId(finished.transcriptId);
      const sm = await summarizeSpeakingSession(currentSessionId);
      setSummary(sm);
      setStatusMessage('已生成会后复盘。');
      await loadSessions();
    } catch (e) {
      setError(typeof e === 'string' ? e : '结束会话失败');
    }
  };

  const onScore = async () => {
    if (!transcriptId) return;
    setError('');
    try {
      const result = await scoreSpeaking(transcriptId);
      setScoreResult(result);
    } catch (e) {
      setError(typeof e === 'string' ? e : '评分失败');
    }
  };

  const onSaveSummaryToNotebook = async () => {
    if (!summary) return;
    setSavingSummary(true);
    setError('');
    try {
      const vocabCandidates = summary.vocabularyCandidates || [];
      for (const item of vocabCandidates.slice(0, 3)) {
        // eslint-disable-next-line no-await-in-loop
        await addVocabularyWord({
          word: item.word,
          definition: item.definition || 'Extracted from speaking review',
          examples: item.examples || [],
          pronunciation: '',
          part_of_speech: 'phrase',
          tags: ['speaking', 'review'],
          source_module: 'speaking',
        });
      }

      const drills = summary.drills || [];
      for (const drill of drills.slice(0, 2)) {
        // eslint-disable-next-line no-await-in-loop
        await createMistake({
          module: 'speaking',
          question_id: `speaking_review_${Date.now()}`,
          question_type: 'speaking_assessment',
          error_type: 'speaking_general_low_band',
          content: `口语复盘建议：${drill}`,
          user_answer: 'N/A',
          correct_answer: 'N/A',
          explanation: drill,
          difficulty: 'medium',
          tags: ['speaking_review', 'coach_followup'],
        });
      }
      setStatusMessage('复盘要点已同步到词汇本和错题本。');
    } catch (e) {
      setError(typeof e === 'string' ? e : '保存复盘失败');
    } finally {
      setSavingSummary(false);
    }
  };

  return (
    <div className="home-page web-dashboard speaking-page">
      <TopNav />
      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>

        <div className="content-area content-shell">
          <div className="web-page-head">
            <div>
              <h2>口语练习</h2>
              <p>会话、分段训练、评分与复盘一体化。</p>
            </div>
            <div className="web-page-head-actions">
              <button onClick={loadSessions}>刷新会话</button>
            </div>
          </div>
          {replayNotice && (
            <div className="card" style={{ marginBottom: 16, borderColor: '#7bb5ff', background: '#f3f8ff' }}>
              <h3>错题重练指引</h3>
              <p>{replayNotice}</p>
              <button onClick={() => navigate('/mistakes?module=speaking&questionType=speaking_assessment')}>返回错题本</button>
            </div>
          )}

          <PageSection title="会话与模式">
            <ToolbarRow>
              <button onClick={onCreateSession}>创建对练会话</button>
              <label>模式：</label>
              <select value={currentMode} onChange={(e) => setCurrentMode(e.target.value)}>
                <option value="coach">教练模式</option>
                <option value="exam">考试模式</option>
              </select>
              <label>
                <input
                  type="checkbox"
                  checked={voiceConfig.withAudio}
                  onChange={(e) => setVoiceConfig((prev) => ({ ...prev, withAudio: e.target.checked }))}
                  style={{ marginRight: 4 }}
                />
                考官语音
              </label>
              <input
                value={voiceConfig.voice}
                onChange={(e) => setVoiceConfig((prev) => ({ ...prev, voice: e.target.value }))}
                placeholder="voice"
                style={{ width: 88 }}
              />
              <button disabled={!currentSessionId} onClick={onFinishAndReview}>结束并生成复盘</button>
              <button disabled={!transcriptId} onClick={onScore}>生成评分</button>
            </ToolbarRow>
            <MetricGrid>
              <MetricCard label="当前会话" value={currentSessionId || '无'} />
              <MetricCard label="当前 Part" value={String(partIndex)} hint={currentPartPrompt || '未开始'} />
              <MetricCard
                label="计时状态"
                value={partPrepRemaining > 0 ? `${partPrepRemaining}s` : `${answerElapsed}s`}
                hint={partPrepRemaining > 0 ? '准备倒计时' : `目标 ${partTargetSeconds}s`}
              />
            </MetricGrid>
            {promptAudioUrl && <audio controls src={promptAudioUrl} style={{ width: '100%', marginTop: 6 }} />}
            <p>
              {partPrepRemaining > 0
                ? `Part准备倒计时：${partPrepRemaining}s`
                : `本轮已用时：${answerElapsed}s / 目标${partTargetSeconds}s`}
            </p>
            {statusMessage && <p style={{ color: '#0f766e' }}>{statusMessage}</p>}
          </PageSection>

          <PageSection title="连续对练">
            <ToolbarRow>
              <button disabled={!currentSessionId} onClick={() => onSwitchPart(1)}>Part1</button>
              <button disabled={!currentSessionId} onClick={() => onSwitchPart(2)}>Part2</button>
              <button disabled={!currentSessionId} onClick={() => onSwitchPart(3)}>Part3</button>
            </ToolbarRow>
            <textarea
              value={turnText}
              onChange={(e) => setTurnText(e.target.value)}
              rows={4}
              placeholder="输入本轮你的回答..."
              style={{ width: '100%', marginBottom: 8 }}
            />
            <button
              disabled={!currentSessionId || !turnText.trim() || partPrepRemaining > 0}
              onClick={onSubmitTurn}
            >
              {partPrepRemaining > 0 ? '准备中...' : '提交本轮回答'}
            </button>

            <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
              {turnRecords.map((x, idx) => (
                <div key={`${x.partIndex}_${x.turnIndex}_${idx}`} style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: 10 }}>
                  <p><strong>Part{x.partIndex} · Round{x.turnIndex}</strong></p>
                  <p>考官主问题：{x.examinerPrompt}</p>
                  {x.examinerPromptAudioUrl && <audio controls src={x.examinerPromptAudioUrl} style={{ width: '100%', marginBottom: 6 }} />}
                  <p>我的回答：{x.userText}</p>
                  <p>追问：{x.followUpQuestion}</p>
                  {x.followUpAudioUrl && <audio controls src={x.followUpAudioUrl} style={{ width: '100%', marginBottom: 6 }} />}
                  <p>反馈（内容）：{x.feedback.content}</p>
                  <p>反馈（语言）：{x.feedback.language}</p>
                  <p>节奏：{x.spentSeconds || 0}s / 目标 {x.targetSeconds || 45}s | {x.pacingFeedback || '-'}</p>
                </div>
              ))}
              {turnRecords.length === 0 && <p>暂无对练记录</p>}
            </div>
          </PageSection>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>会后复盘</h3>
            {summary ? (
              <div>
                <p>模式：{summary.mode} | 转写词数：{summary.transcriptWordCount}</p>
                <p>
                  总用时：{summary.timingSummary?.total_spent_seconds || 0}s |
                  按时轮次：{summary.timingSummary?.on_time_turns || 0}/{summary.timingSummary?.total_turns || 0}
                </p>
                <p>亮点表达：{(summary.highlights || []).join(' / ') || '暂无'}</p>
                <p>替换建议：</p>
                <ul>
                  {(summary.replacements || []).map((r, idx) => (
                    <li key={idx}>{r.from} → {r.to}</li>
                  ))}
                </ul>
                <p>下次必练：</p>
                <ul>
                  {(summary.drills || []).map((d, idx) => <li key={idx}>{d}</li>)}
                </ul>
                {(summary.partStats || []).length > 0 && (
                  <>
                    <p>分段表现：</p>
                    <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 10 }}>
                      <thead>
                        <tr>
                          <th align="left">Part</th>
                          <th align="left">轮次</th>
                          <th align="left">平均词数</th>
                          <th align="left">平均用时</th>
                          <th align="left">按时率</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(summary.partStats || []).map((x) => (
                          <tr key={`part-${x.part_index}`}>
                            <td>{x.part_index}</td>
                            <td>{x.turns}</td>
                            <td>{x.avg_words}</td>
                            <td>{x.avg_spent_seconds}s / {x.target_seconds}s</td>
                            <td>{Math.round((x.on_time_rate || 0) * 100)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
                {summary.bandHints && (
                  <p>
                    预估维度提示：FC {summary.bandHints.fc_hint} | LR {summary.bandHints.lr_hint} |
                    GR {summary.bandHints.gr_hint} | PR {summary.bandHints.pr_hint}
                  </p>
                )}
                <button onClick={onSaveSummaryToNotebook} disabled={savingSummary}>
                  {savingSummary ? '同步中...' : '一键同步到词汇本与错题本'}
                </button>
              </div>
            ) : <p>暂无复盘，请先结束会话生成。</p>}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <h3>历史会话</h3>
            <button onClick={loadSessions}>刷新</button>
            <ul>
              {sessions.map((s) => (
                <li key={s.id}>
                  {s.id} | topic: {s.topic || 'General'} | transcript: {s.transcript_id || '-'}
                  <button style={{ marginLeft: 8 }} onClick={() => setCurrentSessionId(s.id)}>设为当前</button>
                </li>
              ))}
              {sessions.length === 0 && <li>暂无会话</li>}
            </ul>
          </div>

          <div className="card">
            <h3>评分结果</h3>
            {scoreResult ? (
              <div>
                <p>overall: {scoreResult.overall}</p>
                <p>FC: {scoreResult.scores?.FC} | LR: {scoreResult.scores?.LR} | GR: {scoreResult.scores?.GR} | PR: {scoreResult.scores?.PR}</p>
                <button
                  onClick={() => navigate('/mistakes?module=speaking&questionType=speaking_assessment')}
                  style={{ marginBottom: 8 }}
                >
                  查看口语薄弱项
                </button>
                <ul>
                  {(scoreResult.rationales || []).map((r, idx) => <li key={idx}>{r}</li>)}
                </ul>
              </div>
            ) : <p>暂无评分结果</p>}
            {error && <p style={{ color: 'red' }}>{error}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Speaking;
