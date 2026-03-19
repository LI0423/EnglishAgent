import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { getCurrentUser, getChatHistory, getChatSessions, postChatMessage } from '../utils/api';

const Chat = () => {
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
    { to: '/profile', label: '👤 个人中心' },
  ];

  const [userData, setUserData] = useState({ username: '同学' });
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [isComposing, setIsComposing] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [enableAgenticRag, setEnableAgenticRag] = useState(false);
  const [shortMemoryWindow, setShortMemoryWindow] = useState(6);
  const [longMemoryTopK, setLongMemoryTopK] = useState(3);
  const [longMemoryTTL, setLongMemoryTTL] = useState(604800);
  const [minCitationCoverage, setMinCitationCoverage] = useState(0.4);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '你好，我可以帮你做词汇解释、深度搜索和学习建议。',
      rag: null,
    },
  ]);
  const [sessionId, setSessionId] = useState(() => `chat_${Date.now()}`);
  const [sessionList, setSessionList] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [sessionsExpanded, setSessionsExpanded] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const user = await getCurrentUser();
        if (user) {
          setUserData((prev) => ({ ...prev, username: user.username || '同学' }));
        } else {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: '登录状态已失效，请重新登录后再使用智能对话。', rag: null },
          ]);
          navigate('/login');
        }
      } catch (err) {
        console.error('Failed to fetch user data:', err);
      }
    };
    fetchUserData();
  }, []);

  const refreshSessions = async () => {
    setLoadingSessions(true);
    try {
      const sessions = await getChatSessions(40);
      setSessionList(sessions);
    } finally {
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    refreshSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending]);

  const ragConfig = useMemo(() => ({
    short_memory_window: Number(shortMemoryWindow),
    long_memory_top_k: Number(longMemoryTopK),
    long_memory_ttl_seconds: Number(longMemoryTTL),
    min_citation_coverage: Number(minCitationCoverage),
  }), [shortMemoryWindow, longMemoryTopK, longMemoryTTL, minCitationCoverage]);

  const sendMessage = async () => {
    const query = input.trim();
    if (!query || sending) return;

    setMessages((prev) => [...prev, { role: 'user', content: query, rag: null }]);
    setInput('');
    setSending(true);
    try {
      const data = await postChatMessage(query, sessionId, {
        enableAgenticRag,
        ragConfig: enableAgenticRag ? ragConfig : null,
      });

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data?.response || '暂无响应',
          rag: data?.rag || null,
        },
      ]);
      refreshSessions();
    } catch (err) {
      const errMsg = typeof err === 'string' ? err : (err?.message || '请求失败，请稍后重试。');
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: errMsg,
          rag: null,
        },
      ]);
      if (errMsg.includes('登录状态已失效') || errMsg.includes('Invalid token')) {
        navigate('/login');
      }
    } finally {
      setSending(false);
    }
  };

  const handleNewSession = () => {
    const nextSessionId = `chat_${Date.now()}`;
    setSessionId(nextSessionId);
    setMessages([
      {
        role: 'assistant',
        content: '你好，我可以帮你做词汇解释、深度搜索和学习建议。',
        rag: null,
      },
    ]);
  };

  const handleReplaySession = async (targetSessionId) => {
    if (!targetSessionId || targetSessionId === sessionId) return;
    setSessionId(targetSessionId);
    const rows = await getChatHistory(targetSessionId, 200);
    if (!rows.length) {
      setMessages([
        {
          role: 'assistant',
          content: '该会话暂无历史消息。',
          rag: null,
        },
      ]);
      return;
    }
    setMessages(
      rows.map((row) => ({
        role: row.role === 'user' ? 'user' : 'assistant',
        content: row.content || '',
        rag: row.meta?.rag || null,
      })),
    );
  };

  return (
    <div className="chat-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left">
            <h1>🎓 IELTS Agent</h1>
          </div>
          <div className="nav-right">
            <div className="user-profile">
              <span className="avatar">👤</span>
              <span className="username">{userData.username}</span>
            </div>
          </div>
        </div>
      </header>

      <div className="main-layout">
        <div className="sidebar">
          <div className="sidebar-header">
            <h2>🎓 IELTS Agent</h2>
          </div>
          <nav className="sidebar-nav">
            <ul>
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) => `sidebar-nav-link${isActive ? ' active' : ''}`}
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <div className="content-area">
          <main className={`chat-content ${sessionsExpanded ? 'has-session-drawer' : ''}`}>
            <section className="chat-session-toolbar">
              <button type="button" className="chat-session-toggle" onClick={() => setSessionsExpanded((v) => !v)}>
                {sessionsExpanded ? '收起历史会话' : '展开历史会话'}
              </button>
              <button type="button" className="chat-session-new" onClick={handleNewSession}>
                新建会话
              </button>
              <span className="chat-session-current">当前会话：{sessionId}</span>
            </section>

            <aside className={`chat-session-drawer ${sessionsExpanded ? 'open' : ''}`}>
              <div className="chat-session-header">
                <h3>历史会话</h3>
                <div className="chat-session-actions">
                  <button type="button" onClick={refreshSessions} disabled={loadingSessions}>
                    刷新
                  </button>
                  <button type="button" onClick={() => setSessionsExpanded(false)}>
                    关闭
                  </button>
                </div>
              </div>
              <div className="chat-session-list">
                {sessionList.length === 0 && <p className="chat-session-empty">暂无历史会话</p>}
                {sessionList.map((s) => (
                  <button
                    key={s.session_id}
                    type="button"
                    className={`chat-session-item${sessionId === s.session_id ? ' active' : ''}`}
                    onClick={() => handleReplaySession(s.session_id)}
                  >
                    <div className="chat-session-item-title">{s.session_id}</div>
                    <div className="chat-session-item-preview">{s.last_preview || '（无内容）'}</div>
                    <div className="chat-session-item-meta">消息数: {s.message_count}</div>
                  </button>
                ))}
              </div>
            </aside>

            <div className="chat-header">
              <h2>🤖 智能对话</h2>
              <button className="chat-settings-btn" onClick={() => setShowAdvanced((v) => !v)}>
                {showAdvanced ? '收起高级设置' : '展开高级设置'}
              </button>
            </div>

            {showAdvanced && (
              <section className="chat-advanced-panel">
                <label className="chat-switch">
                  <input
                    type="checkbox"
                    checked={enableAgenticRag}
                    onChange={(e) => setEnableAgenticRag(e.target.checked)}
                  />
                  启用 Agentic RAG
                </label>

                <div className="chat-advanced-grid">
                  <label>
                    短期记忆窗口
                    <input
                      type="number"
                      min="2"
                      max="20"
                      value={shortMemoryWindow}
                      onChange={(e) => setShortMemoryWindow(e.target.value)}
                    />
                  </label>
                  <label>
                    长期记忆召回条数
                    <input
                      type="number"
                      min="1"
                      max="20"
                      value={longMemoryTopK}
                      onChange={(e) => setLongMemoryTopK(e.target.value)}
                    />
                  </label>
                  <label>
                    长期记忆 TTL(秒)
                    <input
                      type="number"
                      min="60"
                      step="60"
                      value={longMemoryTTL}
                      onChange={(e) => setLongMemoryTTL(e.target.value)}
                    />
                  </label>
                  <label>
                    引用覆盖阈值
                    <input
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      value={minCitationCoverage}
                      onChange={(e) => setMinCitationCoverage(e.target.value)}
                    />
                  </label>
                </div>
              </section>
            )}

            <section className="chat-messages">
              {messages.map((msg, idx) => (
                <article key={idx} className={`chat-message ${msg.role}`}>
                  <div className="chat-message-role">{msg.role === 'user' ? '你' : '助手'}</div>
                  <div className="chat-message-content">{msg.content}</div>
                  {msg.rag && (
                    <div className="chat-rag-meta">
                      {typeof msg.rag.accepted !== 'undefined' && (
                        <span>accepted: {String(msg.rag.accepted)}</span>
                      )}
                      {typeof msg.rag.iterations !== 'undefined' && (
                        <span>iterations: {msg.rag.iterations}</span>
                      )}
                      {msg.rag.fallback_action && <span>fallback: {msg.rag.fallback_action}</span>}
                      {msg.rag.cache_hit && (
                        <span>
                          cache: hit
                          {msg.rag.cache_score != null ? ` (${Number(msg.rag.cache_score).toFixed(3)})` : ''}
                        </span>
                      )}
                      {Array.isArray(msg.rag.memory_context) && msg.rag.memory_context.length > 0 && (
                        <span>memory hits: {msg.rag.memory_context.length}</span>
                      )}
                    </div>
                  )}
                </article>
              ))}
              <div ref={messagesEndRef} />
            </section>

            <section className="chat-input-bar">
              <textarea
                placeholder="输入你的问题..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onCompositionStart={() => setIsComposing(true)}
                onCompositionEnd={() => setIsComposing(false)}
                onKeyDown={(e) => {
                  // 兼容中文输入法组合态：候选词确认阶段按回车不触发发送
                  if (isComposing || e.nativeEvent?.isComposing || e.keyCode === 229) {
                    return;
                  }
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
              />
              <button onClick={sendMessage} disabled={sending || !input.trim()}>
                {sending ? '发送中...' : '发送'}
              </button>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
};

export default Chat;
