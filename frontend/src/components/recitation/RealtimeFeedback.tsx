import type { RealtimeData } from '../../recitation/types'

interface RealtimeFeedbackProps {
  data: RealtimeData
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const v = clamp(value, 0, 100)
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-600 mb-1">
        <span>{label}</span>
        <span>{v}</span>
      </div>
      <div className="h-2 bg-gray-200 rounded">
        <div className="h-2 bg-blue-600 rounded" style={{ width: `${v}%` }} />
      </div>
    </div>
  )
}

export default function RealtimeFeedback({ data }: RealtimeFeedbackProps) {
  const progress = clamp(data.progress, 0, 100)
  const r = 28
  const c = 2 * Math.PI * r
  const offset = c - (c * progress) / 100

  const breakdown = data.scores.breakdown || {}
  const accuracy = Number(breakdown.accuracy ?? 0)
  const pronunciation = Number(breakdown.pronunciation ?? 0)
  const fluency = Number(breakdown.fluency ?? 0)
  const semantic = Number(breakdown.semantic ?? 0)

  const alerts = data.alerts || []

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-lg font-semibold mb-4">实时反馈</h2>

      <div className="flex items-center gap-4 mb-6">
        <div className="relative w-20 h-20">
          <svg className="w-20 h-20" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r={r} stroke="#e5e7eb" strokeWidth="8" fill="none" />
            <circle
              cx="40"
              cy="40"
              r={r}
              stroke="#2563eb"
              strokeWidth="8"
              fill="none"
              strokeDasharray={c}
              strokeDashoffset={offset}
              strokeLinecap="round"
              transform="rotate(-90 40 40)"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center text-sm font-semibold">
            {progress}%
          </div>
        </div>
        <div className="flex-1">
          <div className="text-xs text-gray-600 mb-1">实时转写</div>
          <div className="text-sm text-gray-900 min-h-10">{data.transcript || '...'}</div>
        </div>
      </div>

      <div className="space-y-3 mb-6">
        <ScoreBar label="准确度" value={accuracy} />
        <ScoreBar label="发音" value={pronunciation} />
        <ScoreBar label="流畅度" value={fluency} />
        <ScoreBar label="内容完整性" value={semantic} />
      </div>

      <div>
        <div className="text-xs text-gray-600 mb-2">提示</div>
        {alerts.length === 0 ? (
          <div className="text-sm text-gray-500">暂无</div>
        ) : (
          <ul className="text-sm text-gray-900 space-y-1">
            {alerts.map((a, i) => (
              <li key={i} className="bg-gray-50 border rounded px-3 py-2">
                {a}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
