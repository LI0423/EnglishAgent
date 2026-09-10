import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  collectBookWord,
  getBookPracticeOptions,
  getVocabularyWordAudio,
  gradeBookWord,
  markBookWordSeen,
  startBookSession,
  uncollectBookWord,
} from '../utils/api'
import WordSelectionPopover from '../components/vocab/WordSelectionPopover'
import WordExplainPanel from '../components/vocab/WordExplainPanel'
import './VocabularyStudy.css'

const API_BASE = String(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')
const AUTO_ADVANCE_MS = 1200
const PRACTICE_MAX_PER_BATCH = 3
const PRACTICE_FORGOT_MAX = 2 // 为「模糊」预留最后一个练习额度

const RATING_OPTIONS = [
  { rating: 'forgot', label: '不认识', hint: '完全没印象', tone: 'danger' },
  { rating: 'fuzzy', label: '模糊', hint: '有印象但说不准', tone: 'warn' },
  { rating: 'familiar', label: '认识', hint: '能准确说出意思', tone: 'ok' },
]

const toAudioSrc = (url) => {
  const raw = String(url || '').trim()
  if (!raw) return ''
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw
  return raw.startsWith('/') ? `${API_BASE}${raw}` : `${API_BASE}/${raw}`
}

function VocabularyStudy() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const count = Math.max(1, Math.min(Number(searchParams.get('count') || 10) || 10, 30))
  const mode = searchParams.get('mode') || 'auto'

  const [words, setWords] = useState([])
  const [index, setIndex] = useState(0)
  const [phase, setPhase] = useState('loading') // loading|front|revealed|feedback|done|empty|error
  const [rating, setRating] = useState('')
  const [gradeResult, setGradeResult] = useState(null)
  const [summary, setSummary] = useState({ forgot: 0, fuzzy: 0, familiar: 0, skipped: 0, collected: 0 })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [explainTarget, setExplainTarget] = useState(null)
  const [practiceMode, setPracticeMode] = useState('') // '' | recognition | spelling
  const [practiceOptions, setPracticeOptions] = useState([])
  const [practiceInput, setPracticeInput] = useState('')
  const [practiceCorrect, setPracticeCorrect] = useState(null)
  const [practiceUsed, setPracticeUsed] = useState(0)
  const [practiceLoading, setPracticeLoading] = useState(false)

  const autoTimerRef = useRef(null)
  const audioRef = useRef(null)
  const cardAreaRef = useRef(null)
  const playTokenRef = useRef(0)

  const total = words.length
  const currentWord = words[index] || null

  const clearAutoTimer = useCallback(() => {
    if (autoTimerRef.current) {
      window.clearTimeout(autoTimerRef.current)
      autoTimerRef.current = null
    }
  }, [])

  const stopAudio = useCallback(() => {
    playTokenRef.current += 1 // 让进行中的 playAudio 请求作废，避免切词后播上一个词
    const audio = audioRef.current
    if (audio) {
      audio.onended = null
      audio.onerror = null
      try { audio.pause() } catch { /* noop */ }
    }
    audioRef.current = null
  }, [])

  const playAudio = useCallback(async (word) => {
    const text = String(word || '').trim()
    stopAudio()
    const token = playTokenRef.current
    if (!text) return
    try {
      const result = await getVocabularyWordAudio(text)
      if (token !== playTokenRef.current) return // 请求返回前已切词/重新播放
      const src = toAudioSrc(result?.audio_url)
      if (!src) return
      const audio = new Audio(src)
      audioRef.current = audio
      audio.onended = () => { if (audioRef.current === audio) audioRef.current = null }
      audio.onerror = () => { if (audioRef.current === audio) audioRef.current = null }
      await audio.play()
    } catch {
      /* 发音失败不阻塞学习 */
    }
  }, [stopAudio])

  const loadSession = useCallback(async () => {
    setPhase('loading')
    setError('')
    try {
      const session = await startBookSession({ count, mode })
      const list = Array.isArray(session?.words) ? session.words : []
      setWords(list)
      setIndex(0)
      setRating('')
      setGradeResult(null)
      setSummary({ forgot: 0, fuzzy: 0, familiar: 0, skipped: 0, collected: 0 })
      setPracticeMode('')
      setPracticeOptions([])
      setPracticeInput('')
      setPracticeCorrect(null)
      setPracticeUsed(0)
      setPracticeLoading(false)
      setPhase(list.length ? 'front' : 'empty')
    } catch (err) {
      setError(typeof err === 'string' ? err : '开启学习失败')
      setPhase('error')
    }
  }, [count, mode])

  useEffect(() => { loadSession() }, [loadSession])
  useEffect(() => () => { clearAutoTimer(); stopAudio() }, [clearAutoTimer, stopAudio])

  const advance = useCallback(() => {
    clearAutoTimer()
    stopAudio()
    setError('')
    setRating('')
    setGradeResult(null)
    setPracticeMode('')
    setPracticeOptions([])
    setPracticeInput('')
    setPracticeCorrect(null)
    const next = index + 1
    if (next >= total) {
      setPhase('done')
      return
    }
    setIndex(next)
    setPhase('front')
  }, [index, total, clearAutoTimer, stopAudio])

  const reveal = useCallback(() => {
    if (phase !== 'front' || !currentWord) return
    setPhase('revealed')
    playAudio(currentWord.word)
  }, [phase, currentWord, playAudio])

  const finalizeGrade = useCallback(async (value, correct) => {
    if (!currentWord) return false
    setSubmitting(true)
    try {
      const result = await gradeBookWord({
        rating: value,
        practice_correct: correct,
        word: currentWord.word,
        vocab_id: currentWord.vocab_id || '',
        bank_word_id: currentWord.bank_word_id || '',
        definition: currentWord.definition || '',
        examples: currentWord.examples || [],
        pronunciation: currentWord.pronunciation || '',
        part_of_speech: currentWord.part_of_speech || '',
        source_module: currentWord.source_module || 'ielts_bank',
      })
      setGradeResult(result)
      setPracticeCorrect(correct)
      setSummary((prev) => ({
        ...prev,
        [value]: (prev[value] || 0) + 1,
        collected: prev.collected + (result?.collected ? 1 : 0),
      }))
      setPhase('feedback')
      clearAutoTimer()
      autoTimerRef.current = window.setTimeout(() => {
        autoTimerRef.current = null
        advance()
      }, AUTO_ADVANCE_MS)
      return true
    } catch (err) {
      setError(typeof err === 'string' ? err : '保存学习结果失败')
      return false
    } finally {
      setSubmitting(false)
    }
  }, [currentWord, advance, clearAutoTimer])

  const shouldPractice = useCallback((value) => {
    if (practiceUsed >= PRACTICE_MAX_PER_BATCH) return false
    if (value === 'fuzzy') return true
    if (value === 'forgot') return practiceUsed < PRACTICE_FORGOT_MAX
    return false
  }, [practiceUsed])

  const submitRating = useCallback(async (value) => {
    if (!currentWord || submitting || phase === 'feedback' || phase === 'practice') return
    setRating(value)
    if (!shouldPractice(value)) {
      await finalizeGrade(value, null)
      return
    }
    setPracticeCorrect(null)
    setPracticeInput('')
    setPracticeOptions([])
    if (value === 'fuzzy') {
      // 模糊 → L2 拼写
      setPracticeMode('spelling')
      setPhase('practice')
      return
    }
    // 不认识 → L1 再认
    setPracticeMode('recognition')
    setPracticeOptions([])
    setPracticeLoading(true)
    setPhase('practice')
    let options = []
    try {
      const result = await getBookPracticeOptions(currentWord.word, currentWord.definition || '')
      options = Array.isArray(result?.options) ? result.options : []
    } catch {
      options = []
    }
    if (options.length < 2) {
      // 题库不可用：退回直接评分，不消耗练习额度；若评分也失败则回到 revealed，避免卡死
      setPracticeLoading(false)
      const ok = await finalizeGrade(value, null)
      if (!ok) setPhase('revealed')
      return
    }
    setPracticeOptions(options)
    setPracticeLoading(false)
  }, [currentWord, submitting, phase, shouldPractice, finalizeGrade])

  const submitPractice = useCallback(async (correct) => {
    if (submitting || !rating) return
    setPracticeUsed((n) => n + 1)
    setPracticeCorrect(Boolean(correct))
    const ok = await finalizeGrade(rating, Boolean(correct))
    if (!ok) setPhase('revealed')
  }, [submitting, rating, finalizeGrade])

  const skipPractice = useCallback(async () => {
    if (submitting || !rating) return
    // 主动跳过练习：不消耗练习额度，直接按自评评分
    setPracticeCorrect(null)
    const ok = await finalizeGrade(rating, null)
    if (!ok) setPhase('revealed')
  }, [submitting, rating, finalizeGrade])

  const submitSpelling = useCallback(() => {
    if (!currentWord || submitting) return
    const guess = String(practiceInput || '').trim().toLowerCase().replace(/[^a-z'-]/g, '')
    const target = String(currentWord.word || '').trim().toLowerCase()
    submitPractice(guess.length > 0 && guess === target)
  }, [currentWord, submitting, practiceInput, submitPractice])

  const skip = useCallback(async () => {
    if (!currentWord) return
    // 已评分（feedback）或练习中不允许再走「跳过」，否则会在已计数的基础上重复计入 skipped
    if (phase === 'feedback' || phase === 'practice' || phase === 'done') return
    clearAutoTimer()
    setSummary((prev) => ({ ...prev, skipped: prev.skipped + 1 }))
    try {
      await markBookWordSeen({
        word: currentWord.word,
        bank_word_id: currentWord.bank_word_id || '',
        source_module: currentWord.source_module || 'ielts_bank',
        action: 'skip',
      })
    } catch {
      /* 「跳过」即使上报失败也应继续 */
    }
    advance()
  }, [currentWord, phase, advance, clearAutoTimer])

  const toggleCollect = useCallback(async (shouldCollect) => {
    if (!currentWord || submitting) return
    clearAutoTimer() // 用户主动操作后暂停自动前进
    setSubmitting(true)
    try {
      if (shouldCollect) {
        const result = await collectBookWord({
          word: currentWord.word,
          definition: currentWord.definition || '',
          examples: currentWord.examples || [],
          pronunciation: currentWord.pronunciation || '',
          part_of_speech: currentWord.part_of_speech || '',
          source_module: currentWord.source_module || 'ielts_bank',
          bank_word_id: currentWord.bank_word_id || '',
        })
        setGradeResult((prev) => ({
          ...(prev || {}),
          in_book: true,
          collected: true,
          vocab_id: result?.vocab_id || prev?.vocab_id || '',
        }))
        setSummary((prev) => ({ ...prev, collected: prev.collected + 1 }))
      } else if (gradeResult?.vocab_id) {
        await uncollectBookWord(gradeResult.vocab_id)
        setGradeResult((prev) => ({ ...(prev || {}), in_book: false, collected: false }))
        setSummary((prev) => ({ ...prev, collected: Math.max(0, prev.collected - 1) }))
      } else {
        setError('该词不在词汇本中，无法移出')
      }
    } catch (err) {
      setError(typeof err === 'string' ? err : '操作失败')
    } finally {
      setSubmitting(false)
    }
  }, [currentWord, submitting, gradeResult, clearAutoTimer])

  const handlePopoverCollect = useCallback(async (word) => {
    const target = String(word || '').trim()
    if (!target) return
    const isCurrent = Boolean(currentWord) && String(currentWord.word || '').toLowerCase() === target.toLowerCase()
    try {
      const result = await collectBookWord({
        word: target,
        definition: isCurrent ? (currentWord.definition || '') : '',
        examples: isCurrent ? (currentWord.examples || []) : [],
        pronunciation: isCurrent ? (currentWord.pronunciation || '') : '',
        part_of_speech: isCurrent ? (currentWord.part_of_speech || '') : '',
        source_module: isCurrent ? (currentWord.source_module || 'manual') : 'manual',
        bank_word_id: isCurrent ? (currentWord.bank_word_id || '') : '',
      })
      if (isCurrent) {
        setGradeResult((prev) => (prev
          ? { ...prev, in_book: true, vocab_id: result?.vocab_id || prev.vocab_id || '' }
          : prev))
      }
    } catch (err) {
      setError(typeof err === 'string' ? err : '加入词汇本失败')
    }
  }, [currentWord])

  const handleCollected = useCallback((word, vocabId) => {
    const target = String(word || '').trim().toLowerCase()
    setExplainTarget((prev) => (prev ? { ...prev, inBook: true } : prev))
    if (currentWord && String(currentWord.word || '').toLowerCase() === target) {
      setGradeResult((prev) => (prev
        ? { ...prev, in_book: true, collected: true, vocab_id: vocabId || prev.vocab_id || '' }
        : prev))
    }
  }, [currentWord])

  const openExplain = useCallback((word) => {
    const target = String(word || '').trim()
    if (!target) return
    const example = (currentWord?.examples || [])[0] || ''
    setExplainTarget({
      word: target,
      context: example,
      inBook: String(currentWord?.word || '').toLowerCase() === target.toLowerCase() && Boolean(currentWord?.in_book),
    })
  }, [currentWord])

  const closeExplain = useCallback(() => setExplainTarget(null), [])

  // 键盘快捷键
  useEffect(() => {
    const onKeyDown = (event) => {
      const key = String(event.key || '').toLowerCase()
      if (phase === 'front') {
        if (event.code === 'Space' || key === 'enter') {
          event.preventDefault()
          reveal()
        } else if (key === 's') {
          skip()
        }
      } else if (phase === 'revealed') {
        if (key === '1') submitRating('forgot')
        else if (key === '2') submitRating('fuzzy')
        else if (key === '3') submitRating('familiar')
        else if (key === 's') skip()
        else if (key === 'p' && currentWord) playAudio(currentWord.word)
      } else if (phase === 'practice') {
        if (key === 's') {
          skipPractice()
        } else if (practiceMode === 'recognition' && /^[1-4]$/.test(key)) {
          const option = practiceOptions[Number(key) - 1]
          if (option) submitPractice(Boolean(option.correct))
        }
      } else if (phase === 'feedback') {
        if (key === 'arrowright' || key === 'n') advance()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [phase, reveal, skip, submitRating, advance, playAudio, currentWord, practiceMode, practiceOptions, submitPractice, skipPractice])

  const progressPct = total > 0 ? Math.round((Math.min(index + 1, total) / total) * 100) : 0

  const renderHeader = () => (
    <>
      <div className="vs-header">
        <button className="vs-link-btn" type="button" onClick={() => navigate('/vocabulary')}>返回词汇本</button>
        <span className="vs-header-title">
          {mode === 'bank' ? '词库学习' : mode === 'review' ? '词汇本复习' : '词汇本学习'}
        </span>
        <span className="vs-header-meta">
          {error && <span style={{ color: '#dc2626' }}>{error}</span>}
          <span className="vs-chip">本批 {total ? Math.min(index + 1, total) : 0}/{total}</span>
        </span>
      </div>
      <div className="vs-progress">
        <div className="vs-progress-bar" style={{ width: `${progressPct}%` }} />
      </div>
    </>
  )

  const renderCard = () => {
    if (phase === 'loading') return <p className="vs-status">正在准备今日词汇…</p>
    if (phase === 'empty') {
      return (
        <div className="vs-card">
          <p className="vs-status">暂时没有需要学习的词汇。</p>
          <div className="vs-actions">
            <button className="vs-btn vs-btn-ghost" type="button" onClick={loadSession}>换一批</button>
            <button className="vs-btn vs-btn-primary" type="button" onClick={() => navigate('/vocabulary')}>返回词汇本</button>
          </div>
        </div>
      )
    }
    if (phase === 'error') {
      return (
        <div className="vs-card">
          <div className="vs-error">{error || '加载失败'}</div>
          <div className="vs-actions">
            <button className="vs-btn vs-btn-primary" type="button" onClick={loadSession}>重试</button>
            <button className="vs-btn vs-btn-ghost" type="button" onClick={() => navigate('/vocabulary')}>返回词汇本</button>
          </div>
        </div>
      )
    }
    if (phase === 'done') {
      return (
        <div className="vs-card">
          <div className="vs-feedback-title">本批完成 🎉</div>
          <p className="vs-meta-line">这一批你过完了 {total} 个词。</p>
          <div className="vs-summary">
            <div className="vs-summary-item"><div className="vs-summary-num">{summary.familiar}</div><div className="vs-summary-label">认识</div></div>
            <div className="vs-summary-item"><div className="vs-summary-num">{summary.fuzzy}</div><div className="vs-summary-label">模糊</div></div>
            <div className="vs-summary-item"><div className="vs-summary-num">{summary.forgot}</div><div className="vs-summary-label">不认识</div></div>
            <div className="vs-summary-item"><div className="vs-summary-num">{summary.skipped}</div><div className="vs-summary-label">跳过</div></div>
            <div className="vs-summary-item"><div className="vs-summary-num">{summary.collected}</div><div className="vs-summary-label">入本</div></div>
          </div>
          <div className="vs-actions">
            <button className="vs-btn vs-btn-primary" type="button" onClick={loadSession}>再来一组</button>
            <button className="vs-btn vs-btn-ghost" type="button" onClick={() => navigate('/vocabulary')}>返回词汇本</button>
          </div>
        </div>
      )
    }
    if (!currentWord) return <p className="vs-status">正在准备今日词汇…</p>

    if (phase === 'front') {
      return (
        <div className="vs-card is-front" onClick={reveal} role="button" tabIndex={0}>
          <h2 className="vs-word">{currentWord.word}</h2>
          {currentWord.pronunciation && <p className="vs-phonetic">/{currentWord.pronunciation}/</p>}
          <p className="vs-hint">点一下看释义</p>
          <div className="vs-actions">
            <button className="vs-btn vs-btn-ghost" type="button" onClick={(e) => { e.stopPropagation(); skip() }}>
              见过但不想学，跳过
            </button>
          </div>
        </div>
      )
    }

    if (phase === 'revealed') {
      const example = (currentWord.examples || [])[0]
      return (
        <div className="vs-card">
          <h2 className="vs-word">{currentWord.word}</h2>
          {currentWord.pronunciation && <p className="vs-phonetic">/{currentWord.pronunciation}/</p>}
          <button className="vs-audio-btn" type="button" onClick={() => playAudio(currentWord.word)}>🔊 播放发音</button>
          <p className="vs-definition">{currentWord.definition || '暂无释义'}</p>
          {currentWord.part_of_speech && <p className="vs-meta-line">{currentWord.part_of_speech}</p>}
          {example && <p className="vs-example">{example}</p>}
          <div className="vs-rating-grid">
            {RATING_OPTIONS.map((option) => (
              <button
                className={`vs-rating-btn tone-${option.tone}`}
                key={option.rating}
                type="button"
                disabled={submitting}
                onClick={() => submitRating(option.rating)}
              >
                <span className="vs-rating-label">{option.label}</span>
                <span className="vs-rating-hint">{option.hint}</span>
              </button>
            ))}
          </div>
          <div className="vs-actions">
            <button className="vs-btn vs-btn-ghost" type="button" onClick={() => openExplain(currentWord.word)}>问老师</button>
            <button className="vs-btn vs-btn-ghost" type="button" onClick={skip}>跳过</button>
          </div>
        </div>
      )
    }

    if (phase === 'practice') {
      if (practiceLoading) {
        return (
          <div className="vs-card">
            <h2 className="vs-word">{currentWord.word}</h2>
            <p className="vs-status">正在准备练习…</p>
          </div>
        )
      }
      if (practiceMode === 'spelling') {
        return (
          <div className="vs-card">
            <div className="vs-practice-tag">拼写练习 · 根据释义写出单词</div>
            <p className="vs-definition">{currentWord.definition || '暂无释义'}</p>
            <form className="vs-spell-form" onSubmit={(event) => { event.preventDefault(); submitSpelling() }}>
              <input
                className="vs-spell-input"
                value={practiceInput}
                autoFocus
                autoComplete="off"
                spellCheck={false}
                onChange={(event) => setPracticeInput(event.target.value)}
                placeholder="输入英文单词"
              />
              <button className="vs-btn vs-btn-primary" type="submit" disabled={submitting || !practiceInput.trim()}>
                提交
              </button>
            </form>
            <div className="vs-actions">
              <button className="vs-btn vs-btn-ghost" type="button" disabled={submitting} onClick={skipPractice}>
                跳过练习，直接评分
              </button>
            </div>
          </div>
        )
      }
      return (
        <div className="vs-card">
          <div className="vs-practice-tag">再认练习 · 选出最接近的意思</div>
          <h2 className="vs-word">{currentWord.word}</h2>
          <div className="vs-choice-grid">
            {practiceOptions.map((option, i) => (
              <button
                className="vs-choice-option"
                key={`${i}-${option.definition}`}
                type="button"
                disabled={submitting}
                onClick={() => submitPractice(Boolean(option.correct))}
              >
                <span className="vs-choice-key">{i + 1}</span>
                {option.definition}
              </button>
            ))}
          </div>
          <div className="vs-actions">
            <button className="vs-btn vs-btn-ghost" type="button" disabled={submitting} onClick={skipPractice}>
              跳过练习，直接评分
            </button>
          </div>
        </div>
      )
    }

    // feedback
    const inBook = Boolean(gradeResult?.in_book)
    const newlyCollected = Boolean(gradeResult?.collected)
    return (
      <div className="vs-card">
        <h2 className="vs-word">{currentWord.word}</h2>
        <p className="vs-definition">{currentWord.definition || '暂无释义'}</p>
        <div className={`vs-collect-state ${inBook ? 'is-in' : 'is-out'}`}>
          {inBook ? (newlyCollected ? '✓ 已加入词汇本' : '✓ 已在词汇本') : '未加入词汇本'}
        </div>
        {practiceCorrect !== null && (
          <p className={`vs-practice-result ${practiceCorrect ? 'is-ok' : 'is-bad'}`}>
            {practiceMode === 'spelling' ? '拼写练习' : '再认练习'}：
            {practiceCorrect ? '答对了 ✅' : `答错了，正确答案是 ${currentWord.word}`}
          </p>
        )}
        <p className="vs-nextline">
          {gradeResult?.skipped
            ? '已记为「见过」，不进入复习队列。'
            : (gradeResult?.next_review_label || '复习间隔已更新。')}
        </p>
        <div className="vs-actions">
          {inBook
            ? <button className="vs-btn vs-btn-ghost" type="button" disabled={submitting} onClick={() => toggleCollect(false)}>移出词汇本</button>
            : <button className="vs-btn vs-btn-ghost" type="button" disabled={submitting} onClick={() => toggleCollect(true)}>加入词汇本</button>}
          <button className="vs-btn vs-btn-primary" type="button" onClick={advance}>
            {index + 1 >= total ? '完成本批 →' : '下一个 →'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="vs-page">
      {renderHeader()}
      <div className="vs-body" ref={cardAreaRef}>
        {renderCard()}
      </div>
      <WordSelectionPopover
        containerRef={cardAreaRef}
        onCollect={handlePopoverCollect}
        onExplain={openExplain}
      />
      {explainTarget && (
        <WordExplainPanel
          word={explainTarget.word}
          context={explainTarget.context}
          inBook={explainTarget.inBook}
          onClose={closeExplain}
          onCollected={handleCollected}
        />
      )}
    </div>
  )
}

export default VocabularyStudy
