import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { bulkRemoveBookWords, getBookList, getBookSummary } from '../utils/api'
import './VocabularyBook.css'

const PAGE_SIZE = 50

const STATUS_TABS = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '学习中' },
  { key: 'mastered', label: '已掌握' },
]

const EMPTY_SUMMARY = { total: 0, active_count: 0, mastered_count: 0, due_count: 0, groups: [] }

function VocabularyBook() {
  const navigate = useNavigate()
  const [summary, setSummary] = useState(EMPTY_SUMMARY)
  const [source, setSource] = useState('')
  const [status, setStatus] = useState('all')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(() => new Set())
  const [removing, setRemoving] = useState(false)
  const reqIdRef = useRef(0)
  const summaryReqRef = useRef(0)

  const loadSummary = useCallback(async () => {
    const myReq = ++summaryReqRef.current
    try {
      const data = await getBookSummary()
      if (myReq !== summaryReqRef.current) return
      setSummary({ ...EMPTY_SUMMARY, ...(data || {}) })
    } catch (err) {
      if (myReq === summaryReqRef.current) setError(typeof err === 'string' ? err : '获取词汇本概览失败')
    }
  }, [])

  const loadPage = useCallback(async (nextOffset = 0) => {
    const myReq = ++reqIdRef.current
    setLoading(true)
    setError('')
    try {
      const data = await getBookList({ source, status, limit: PAGE_SIZE, offset: nextOffset })
      if (myReq !== reqIdRef.current) return // 已切换筛选，丢弃过期响应
      const list = Array.isArray(data?.items) ? data.items : []
      setTotal(Number(data?.total) || 0)
      setOffset(nextOffset)
      setItems((prev) => (nextOffset === 0 ? list : [...prev, ...list]))
    } catch (err) {
      if (myReq === reqIdRef.current) setError(typeof err === 'string' ? err : '获取词汇本列表失败')
    } finally {
      if (myReq === reqIdRef.current) setLoading(false)
    }
  }, [source, status])

  useEffect(() => { loadSummary() }, [loadSummary])
  useEffect(() => {
    setSelected(new Set())
    loadPage(0)
  }, [loadPage])

  const toggleOne = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(items.map((item) => item.id)))
  }

  const removeSelected = async () => {
    if (!selected.size || removing) return
    if (typeof window !== 'undefined' && !window.confirm(`确认把选中的 ${selected.size} 个词移出词汇本？`)) return
    setRemoving(true)
    try {
      await bulkRemoveBookWords([...selected])
      setSelected(new Set())
      await Promise.all([loadSummary(), loadPage(0)])
    } catch (err) {
      setError(typeof err === 'string' ? err : '批量移出失败')
    } finally {
      setRemoving(false)
    }
  }

  const hasMore = items.length < total

  return (
    <div className="vb-page">
      <div className="vb-header">
        <button className="vb-link-btn" type="button" onClick={() => navigate('/vocabulary')}>返回词汇本</button>
        <span className="vb-header-title">词汇本管理</span>
        <span className="vb-header-meta">
          {error ? <span className="vb-error">{error}</span> : `共 ${summary.total} 词`}
        </span>
      </div>

      <div className="vb-body">
        <div className="vb-stats">
          <div className="vb-stat"><div className="vb-stat-num">{summary.total}</div><div className="vb-stat-label">词汇总数</div></div>
          <div className="vb-stat"><div className="vb-stat-num">{summary.active_count}</div><div className="vb-stat-label">学习中</div></div>
          <div className="vb-stat"><div className="vb-stat-num">{summary.mastered_count}</div><div className="vb-stat-label">已掌握</div></div>
          <div className="vb-stat"><div className="vb-stat-num">{summary.due_count}</div><div className="vb-stat-label">到期复习</div></div>
        </div>

        <div className="vb-filters">
          <div className="vb-row">
            <button
              className={`vb-chip ${source === '' ? 'is-active' : ''}`}
              type="button"
              onClick={() => setSource('')}
            >
              全部来源 {summary.total}
            </button>
            {(summary.groups || []).map((group) => (
              <button
                key={group.source_module}
                className={`vb-chip ${source === group.source_module ? 'is-active' : ''}`}
                type="button"
                onClick={() => setSource(group.source_module)}
              >
                {group.label} {group.count}
              </button>
            ))}
          </div>

          <div className="vb-tabs">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.key}
                className={`vb-tab ${status === tab.key ? 'is-active' : ''}`}
                type="button"
                onClick={() => setStatus(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {selected.size > 0 && (
          <div className="vb-bulkbar">
            已选 {selected.size} 个词
            <button type="button" disabled={removing} onClick={removeSelected}>
              {removing ? '处理中…' : '移出词汇本'}
            </button>
          </div>
        )}

        <div className="vb-list">
          <div className="vb-list-head">
            <input
              className="vb-check"
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              aria-label="全选本页"
            />
            <span className="vb-word">单词</span>
            <span className="vb-def">释义</span>
            <span className="vb-source">来源</span>
            <span className="vb-mastery">掌握度</span>
            <span className="vb-badges">状态</span>
          </div>

          {items.map((item) => (
            <div className="vb-item" key={item.id}>
              <input
                className="vb-check"
                type="checkbox"
                checked={selected.has(item.id)}
                onChange={() => toggleOne(item.id)}
                aria-label={`选择 ${item.word}`}
              />
              <span className="vb-word">{item.word}</span>
              <span className="vb-def" title={item.definition}>{item.definition || '暂无释义'}</span>
              <span className="vb-source">{item.source_module || '其他'}</span>
              <span className="vb-mastery">
                <span className="vb-mastery-bar">
                  <span className="vb-mastery-fill" style={{ width: `${Math.round(Math.max(0, Math.min(1, item.mastery_level || 0)) * 100)}%` }} />
                </span>
                <span className="vb-mastery-text">{Math.round((item.mastery_level || 0) * 100)}%</span>
              </span>
              <span className="vb-badges">
                {item.mastered && <span className="vb-badge mastered">已掌握</span>}
                {!item.mastered && item.due && <span className="vb-badge due">待复习</span>}
              </span>
            </div>
          ))}

          {!loading && items.length === 0 && (
            <div className="vb-status">这里还没有词。去「词库学习」或阅读中划词收录吧。</div>
          )}
          {loading && items.length === 0 && <div className="vb-status">加载中…</div>}
        </div>

        {hasMore && (
          <button className="vb-more" type="button" disabled={loading} onClick={() => loadPage(offset + PAGE_SIZE)}>
            {loading ? '加载中…' : `加载更多（${items.length}/${total}）`}
          </button>
        )}
      </div>
    </div>
  )
}

export default VocabularyBook
