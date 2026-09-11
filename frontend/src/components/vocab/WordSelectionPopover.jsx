import { useCallback, useEffect, useRef, useState } from 'react'
import './wordTools.css'

// 只接受「单个英文单词」，避免把整句选中的文本当成查询词
const WORD_PATTERN = /^[A-Za-z][A-Za-z'-]{1,40}$/

/**
 * 划词浮层：在 containerRef 范围内选中一个英文单词后，弹出
 * 「加入词汇本 / 问老师」两个动作。不打断当前学习流程。
 */
function WordSelectionPopover({ containerRef, onCollect, onExplain, enabled = true }) {
  const [selection, setSelection] = useState(null) // { word, x, y }
  const [added, setAdded] = useState(false)
  const timerRef = useRef(null)

  const evaluate = useCallback((insidePopover = false) => {
    // 点浮层自身按钮时不重新评估：否则浏览器折叠选区会让浮层立刻关闭，看不到「已加入 ✓」
    if (insidePopover) return
    if (!enabled || typeof window === 'undefined') return
    const sel = window.getSelection?.()
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
      setSelection(null)
      return
    }
    const text = String(sel.toString() || '').trim()
    if (!WORD_PATTERN.test(text)) {
      setSelection(null)
      return
    }
    const range = sel.getRangeAt(0)
    const container = containerRef?.current
    if (container && !container.contains(range.commonAncestorContainer)) {
      setSelection(null)
      return
    }
    const rect = range.getBoundingClientRect()
    if (!rect || (!rect.width && !rect.height)) {
      setSelection(null)
      return
    }
    // 夹取到视口内，避免屏幕边缘选词时浮层溢出
    const halfWidth = 110
    const rawX = rect.left + rect.width / 2
    const maxX = typeof window !== 'undefined' ? Math.max(halfWidth, window.innerWidth - halfWidth) : rawX
    const x = Math.min(Math.max(rawX, halfWidth), maxX)
    setSelection({ word: text, x, y: rect.top })
    setAdded(false)
  }, [containerRef, enabled])

  useEffect(() => {
    const handler = (event) => {
      const insidePopover = Boolean(event?.target?.closest?.('.ws-popover'))
      if (timerRef.current) window.clearTimeout(timerRef.current)
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null
        evaluate(insidePopover)
      }, 0)
    }
    document.addEventListener('mouseup', handler)
    document.addEventListener('touchend', handler)
    return () => {
      document.removeEventListener('mouseup', handler)
      document.removeEventListener('touchend', handler)
      if (timerRef.current) {
        window.clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [evaluate])

  useEffect(() => {
    if (!selection) return undefined
    const onPointerDown = (event) => {
      if (event.target?.closest?.('.ws-popover')) return
      setSelection(null)
    }
    window.addEventListener('mousedown', onPointerDown)
    return () => window.removeEventListener('mousedown', onPointerDown)
  }, [selection])

  if (!selection) return null

  const handleCollect = async () => {
    setAdded(true)
    try {
      await onCollect?.(selection.word)
    } catch {
      setAdded(false) // 失败回滚，避免一直显示「已加入 ✓」
    }
  }

  return (
    <div
      className="ws-popover"
      style={{ left: `${selection.x}px`, top: `${Math.max(44, selection.y - 8)}px` }}
      role="dialog"
      aria-label="选词操作"
    >
      <span className="ws-popover-word">{selection.word}</span>
      <button className="ws-popover-btn" type="button" disabled={added} onClick={handleCollect}>
        {added ? '已加入 ✓' : '加入词汇本'}
      </button>
      <button
        className="ws-popover-btn ws-popover-btn-primary"
        type="button"
        onClick={() => { onExplain?.(selection.word); setSelection(null) }}
      >
        问老师
      </button>
    </div>
  )
}

export default WordSelectionPopover
