import { useEffect, useMemo, useRef } from 'react'
import type { EvaluationResult } from '../../recitation/types'

interface ResultViewProps {
  result: EvaluationResult
  onRetry: () => void
}

type DiffOp = { type: 'equal' | 'insert' | 'delete'; text: string }

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function diffChars(a: string, b: string): DiffOp[] {
  const A = Array.from(a)
  const B = Array.from(b)
  const n = A.length
  const m = B.length

  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0))
  for (let i = 1; i <= n; i += 1) {
    for (let j = 1; j <= m; j += 1) {
      dp[i][j] = A[i - 1] === B[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }

  const ops: DiffOp[] = []
  let i = n
  let j = m
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && A[i - 1] === B[j - 1]) {
      ops.push({ type: 'equal', text: A[i - 1] })
      i -= 1
      j -= 1
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.push({ type: 'insert', text: B[j - 1] })
      j -= 1
    } else if (i > 0) {
      ops.push({ type: 'delete', text: A[i - 1] })
      i -= 1
    }
  }

  ops.reverse()
  const merged: DiffOp[] = []
  for (const op of ops) {
    const last = merged[merged.length - 1]
    if (last && last.type === op.type) last.text += op.text
    else merged.push({ ...op })
  }
  return merged
}

export default function ResultView({ result, onRetry }: ResultViewProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const score = clamp(result.total_score, 0, 100)
  const breakdown = result.breakdown
  const emotionScore = useMemo(() => {
    const e: any = (result as any).emotion_expression
    const m = e?.match
    const s = e?.scores
    const v = typeof m?.style_match === 'number' ? m.style_match : typeof s?.style_match === 'number' ? s.style_match : 0
    return clamp(Number(v || 0), 0, 100)
  }, [result])
  const intelligent: any = (result as any).intelligent_feedback
  const emotionMeta = useMemo(() => {
    const e: any = (result as any).emotion_expression
    const top1 = e?.detected?.top1
    const target = e?.target
    const match = e?.match
    return {
      top1Label: typeof top1?.label === 'string' ? top1.label : '',
      inBand: typeof match?.in_target_bandwidth === 'boolean' ? match.in_target_bandwidth : null,
      tags: Array.isArray(target?.tags) ? target.tags : [],
    }
  }, [result])

  const ops = useMemo(() => diffChars(result.standard_text, result.transcript), [result.standard_text, result.transcript])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = canvas.width
    const h = canvas.height
    ctx.clearRect(0, 0, w, h)

    const cx = w / 2
    const cy = h / 2
    const radius = Math.min(w, h) * 0.33
    const labels = ['准确度', '发音', '流畅度', '内容完整性', '情感表达'] as const
    const values = [
      clamp(breakdown.accuracy, 0, 100),
      clamp(breakdown.pronunciation, 0, 100),
      clamp(breakdown.fluency, 0, 100),
      clamp(breakdown.semantic, 0, 100),
      emotionScore,
    ]

    const angles = labels.map((_, idx) => (Math.PI * 2 * idx) / labels.length - Math.PI / 2)

    ctx.strokeStyle = '#e5e7eb'
    ctx.lineWidth = 1
    for (let ring = 1; ring <= 4; ring += 1) {
      const r = (radius * ring) / 4
      ctx.beginPath()
      for (let i = 0; i < angles.length; i += 1) {
        const x = cx + Math.cos(angles[i]) * r
        const y = cy + Math.sin(angles[i]) * r
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.closePath()
      ctx.stroke()
    }

    for (let i = 0; i < angles.length; i += 1) {
      const x = cx + Math.cos(angles[i]) * radius
      const y = cy + Math.sin(angles[i]) * radius
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(x, y)
      ctx.stroke()
    }

    ctx.fillStyle = 'rgba(37, 99, 235, 0.22)'
    ctx.strokeStyle = '#2563eb'
    ctx.lineWidth = 2
    ctx.beginPath()
    for (let i = 0; i < angles.length; i += 1) {
      const r = (values[i] / 100) * radius
      const x = cx + Math.cos(angles[i]) * r
      const y = cy + Math.sin(angles[i]) * r
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.closePath()
    ctx.fill()
    ctx.stroke()

    ctx.fillStyle = '#111827'
    ctx.font = '12px sans-serif'
    for (let i = 0; i < labels.length; i += 1) {
      const x = cx + Math.cos(angles[i]) * (radius + 18)
      const y = cy + Math.sin(angles[i]) * (radius + 18)
      ctx.fillText(labels[i], x - 18, y + 4)
    }
  }, [breakdown, emotionScore])

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-600 mb-1">总分</div>
            <div className="text-4xl font-bold">{score}</div>
          </div>
          <button onClick={onRetry} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
            再来一次
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-semibold mb-4">能力雷达图</h2>
        <canvas ref={canvasRef} width={520} height={320} className="w-full bg-gray-50 rounded border" />
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-semibold mb-4">情感表达</h2>
        <div className="text-sm text-gray-600 mb-2">情感匹配度</div>
        <div className="w-full bg-gray-200 rounded h-3 overflow-hidden">
          <div className="h-3 bg-indigo-600" style={{ width: `${emotionScore}%` }} />
        </div>
        <div className="mt-2 text-sm text-gray-700"> {emotionScore} / 100</div>
        <div className="mt-3 text-sm text-gray-600 space-y-1">
          {emotionMeta.top1Label && <div>检测情绪：{emotionMeta.top1Label}</div>}
          {emotionMeta.tags.length > 0 && <div>预期风格：{emotionMeta.tags.join(' / ')}</div>}
          {typeof emotionMeta.inBand === 'boolean' && <div>是否在目标带宽：{emotionMeta.inBand ? '是' : '否'}</div>}
        </div>
        {(result as any).fallback_note && (
          <div className="mt-3 text-sm text-gray-500">{String((result as any).fallback_note)}</div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-semibold mb-4">原文对比</h2>
        <div className="text-sm text-gray-600 mb-2">标准文本</div>
        <div className="p-3 rounded border bg-gray-50 whitespace-pre-wrap">{result.standard_text}</div>

        <div className="text-sm text-gray-600 mt-4 mb-2">识别文本（红色为差异）</div>
        <div className="p-3 rounded border bg-gray-50 whitespace-pre-wrap break-words">
          {ops.map((op, idx) => {
            if (op.type === 'equal') return <span key={idx}>{op.text}</span>
            if (op.type === 'insert') return <span key={idx} className="text-red-600">{op.text}</span>
            return <span key={idx} className="text-red-600 underline">{op.text}</span>
          })}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-semibold mb-4">AI 教师点评</h2>
        {!intelligent ? (
          <div className="text-sm text-gray-500">暂不可用</div>
        ) : (
          <div className="space-y-3">
            <div className="border rounded bg-gray-50 px-3 py-2 text-sm">{intelligent.overall_comment}</div>
            {Array.isArray(intelligent.suggestions) && intelligent.suggestions.length > 0 && (
              <ul className="space-y-2">
                {intelligent.suggestions.map((s: any, i: number) => (
                  <li key={i} className="border rounded bg-gray-50 px-3 py-2 text-sm">{String(s)}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {Array.isArray((result as any).error_details) && (result as any).error_details.length > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold mb-4">错误明细</h2>
          <ul className="space-y-2">
            {(result as any).error_details.map((e: any, i: number) => (
              <li key={i} className="border rounded bg-gray-50 px-3 py-2 text-sm">
                {String(e.type)}：期望 “{String(e.expected)}” 实际 “{String(e.actual)}”
              </li>
            ))}
          </ul>
        </div>
      )}

    </div>
  )
}
