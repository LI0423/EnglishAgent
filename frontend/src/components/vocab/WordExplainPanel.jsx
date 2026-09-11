import { useCallback, useEffect, useRef, useState } from 'react'
import { askAboutWord, collectBookWord, getWordExplanation } from '../../utils/api'
import './wordTools.css'

const QUICK_QUESTIONS = [
  '有什么常见搭配？',
  '和近义词怎么区分？',
  '用雅思写作造个句？',
  '怎么记住这个词？',
]

/**
 * 「问老师」面板：先给词库结构化速览（L0，零延迟），
 * 用户追问时才调用 LLM（L1）。底部可一键加入词汇本。
 */
function WordExplainPanel({ word, context = '', inBook = false, onClose, onCollected }) {
  const [facts, setFacts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [collected, setCollected] = useState(Boolean(inBook))
  const [collecting, setCollecting] = useState(false)
  const [question, setQuestion] = useState('')
  const [thread, setThread] = useState([])
  const [asking, setAsking] = useState(false)
  const bodyRef = useRef(null)
  const reqIdRef = useRef(0)
  const askingRef = useRef(false)
  const lastScrollCountRef = useRef(0)

  useEffect(() => {
    let alive = true
    const myReq = reqIdRef.current + 1
    reqIdRef.current = myReq
    setLoading(true)
    setError('')
    setThread([])
    setCollected(Boolean(inBook))
    getWordExplanation(word, context)
      .then((data) => {
        if (!alive || myReq !== reqIdRef.current) return
        setFacts(data || null)
        setCollected(Boolean(data?.in_book))
      })
      .catch((err) => {
        if (alive && myReq === reqIdRef.current) setError(typeof err === 'string' ? err : '获取讲解失败')
      })
      .finally(() => {
        if (alive && myReq === reqIdRef.current) setLoading(false)
      })
    return () => { alive = false }
  }, [word, context, inBook])

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  // 只在「有新消息」或「正在思考」时滚到底，避免切词/重渲染把释义内容顶走
  useEffect(() => {
    const grew = thread.length > lastScrollCountRef.current
    lastScrollCountRef.current = thread.length
    if ((grew || asking) && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [thread, asking])

  const ask = useCallback(async (text) => {
    const clean = String(text || '').trim()
    if (!clean || askingRef.current) return
    askingRef.current = true
    const myReq = reqIdRef.current
    const history = thread
    setThread((prev) => [...prev, { role: 'user', content: clean }])
    setQuestion('')
    setAsking(true)
    try {
      const result = await askAboutWord({
        word,
        question: clean,
        context,
        definition: (facts?.definitions || [])[0] || '',
        history,
      })
      if (myReq !== reqIdRef.current) return
      setThread((prev) => [...prev, { role: 'assistant', content: result?.answer || '（无回答）' }])
    } catch (err) {
      if (myReq !== reqIdRef.current) return
      setThread((prev) => [...prev, { role: 'assistant', content: typeof err === 'string' ? err : '回答失败，请重试' }])
    } finally {
      askingRef.current = false
      if (myReq === reqIdRef.current) setAsking(false)
    }
  }, [thread, word, context, facts])

  const collect = useCallback(async () => {
    if (collecting || collected) return
    setCollecting(true)
    try {
      const result = await collectBookWord({
        word,
        definition: (facts?.definitions || [])[0] || '',
        examples: facts?.examples || [],
        pronunciation: facts?.pronunciation || '',
        part_of_speech: facts?.part_of_speech || '',
        // 词库词应保留其来源，否则会被归类到「手动添加」
        source_module: facts?.bank_word_id ? 'ielts_bank' : 'manual',
        bank_word_id: facts?.bank_word_id || '',
        context,
      })
      setCollected(true)
      onCollected?.(word, result?.vocab_id)
    } catch (err) {
      setError(typeof err === 'string' ? err : '加入词汇本失败')
    } finally {
      setCollecting(false)
    }
  }, [collecting, collected, word, facts, context, onCollected])

  const closeRef = useRef(null)

  // 打开面板时把焦点移入，关闭后归还给原元素（键盘/读屏用户不会丢焦点）
  useEffect(() => {
    const previous = typeof document !== 'undefined' ? document.activeElement : null
    closeRef.current?.focus()
    return () => {
      if (previous && typeof previous.focus === 'function') previous.focus()
    }
  }, [])

  // Esc 关闭
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <>
      <div className="wp-overlay" onClick={onClose} />
      <aside className="wp-panel" role="dialog" aria-modal="true" aria-label={`${word} 的讲解`}>
        <div className="wp-head">
          <div>
            <div className="wp-word">{facts?.word || word}</div>
            {facts?.pronunciation && <div className="wp-phonetic">/{facts.pronunciation}/</div>}
          </div>
          <button ref={closeRef} className="wp-close" type="button" onClick={onClose}>关闭</button>
        </div>

        <div className="wp-body" ref={bodyRef}>
          {loading && <p className="wp-msg">正在查询…</p>}
          {!loading && error && <p className="wp-error">{error}</p>}
          {!loading && facts && (
            <>
              {!facts.found && (
                <p className="wp-msg">词库里暂时没有「{word}」的条目，你可以直接问老师。</p>
              )}
              {(facts.part_of_speech || facts.difficulty) && (
                <p className="wp-msg">
                  {[facts.part_of_speech, facts.difficulty].filter(Boolean).join(' · ')}
                </p>
              )}
              {(facts.definitions || []).length > 0 && (
                <div className="wp-section">
                  <div className="wp-section-title">释义</div>
                  {facts.definitions.map((item, i) => <p className="wp-def" key={i}>{item}</p>)}
                </div>
              )}
              {(facts.examples || []).length > 0 && (
                <div className="wp-section">
                  <div className="wp-section-title">例句</div>
                  {facts.examples.map((item, i) => <p className="wp-example" key={i}>{item}</p>)}
                </div>
              )}
              {(facts.phrases || []).length > 0 && (
                <div className="wp-section">
                  <div className="wp-section-title">常见搭配</div>
                  <div className="wp-tags">
                    {facts.phrases.map((item, i) => <span className="wp-tag" key={i}>{item}</span>)}
                  </div>
                </div>
              )}
              {((facts.synonyms || []).length > 0 || (facts.related_words || []).length > 0) && (
                <div className="wp-section">
                  <div className="wp-section-title">近义 / 相关</div>
                  <div className="wp-tags">
                    {(facts.synonyms || []).map((item, i) => <span className="wp-tag" key={`s${i}`}>{item}</span>)}
                    {(facts.related_words || []).map((item, i) => <span className="wp-tag" key={`r${i}`}>{item}</span>)}
                  </div>
                </div>
              )}
            </>
          )}

          {thread.length > 0 && (
            <div className="wp-thread">
              {thread.map((message, i) => (
                <div className={`wp-bubble ${message.role === 'user' ? 'user' : 'assistant'}`} key={i}>
                  {message.content}
                </div>
              ))}
              {asking && <div className="wp-bubble assistant">老师正在思考…</div>}
            </div>
          )}
        </div>

        <div className="wp-foot">
          <div className="wp-quick">
            {QUICK_QUESTIONS.map((item, i) => (
              <button key={i} type="button" disabled={asking} onClick={() => ask(item)}>{item}</button>
            ))}
          </div>
          <form className="wp-ask" onSubmit={(event) => { event.preventDefault(); ask(question) }}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="继续追问…"
            />
            <button className="wp-btn wp-btn-primary" type="submit" disabled={asking || !question.trim()}>提问</button>
          </form>
          <div className="wp-actions">
            <button
              className="wp-btn wp-btn-ghost"
              type="button"
              disabled={collecting || collected}
              onClick={collect}
            >
              {collected ? '已在词汇本 ✓' : '加入词汇本'}
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}

export default WordExplainPanel
