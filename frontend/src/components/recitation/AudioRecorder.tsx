import { useEffect, useMemo, useRef, useState } from 'react'

interface AudioRecorderProps {
  estimatedSeconds?: number
  disabled?: boolean
  onStart?: () => void
  onStop?: () => void
  onChunk: (payload: { base64: string; isFinal: boolean }) => void
}

function pad2(n: number) {
  return n.toString().padStart(2, '0')
}

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${pad2(m)}:${pad2(s)}`
}

export default function AudioRecorder({ estimatedSeconds = 30, disabled, onStart, onStop, onChunk }: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [isSilent, setIsSilent] = useState(false)
  const [finalBlob, setFinalBlob] = useState<Blob | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const finalSentRef = useRef(false)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const rafRef = useRef<number | null>(null)

  const timerLabel = useMemo(() => `${formatTime(elapsed)} / 预计${estimatedSeconds}秒`, [elapsed, estimatedSeconds])

  useEffect(() => {
    if (!isRecording) return
    const t = window.setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => window.clearInterval(t)
  }, [isRecording])

  useEffect(() => {
    if (!isRecording) return
    if (elapsed < estimatedSeconds) return
    const recorder = mediaRecorderRef.current
    if (!recorder) return
    if (recorder.state !== 'recording') return
    window.setTimeout(() => {
      if (recorder.state === 'recording') {
        setError(`已达到${estimatedSeconds}秒，自动结束录音`)
        void stop()
      }
    }, 0)
  }, [elapsed, estimatedSeconds, isRecording])

  const drawWaveform = () => {
    const canvas = canvasRef.current
    const analyser = analyserRef.current
    if (!canvas || !analyser) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const bufferLength = analyser.fftSize
    const dataArray = new Uint8Array(bufferLength)

    const draw = () => {
      analyser.getByteTimeDomainData(dataArray)
      let totalDelta = 0
      for (let i = 0; i < dataArray.length; i += 1) totalDelta += Math.abs(dataArray[i] - 128)
      setIsSilent(totalDelta / dataArray.length < 4)
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.lineWidth = 2
      ctx.strokeStyle = '#2563eb'
      ctx.beginPath()

      const sliceWidth = canvas.width / bufferLength
      let x = 0
      for (let i = 0; i < bufferLength; i += 1) {
        const v = dataArray[i] / 128.0
        const y = (v * canvas.height) / 2
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
        x += sliceWidth
      }
      ctx.lineTo(canvas.width, canvas.height / 2)
      ctx.stroke()

      rafRef.current = requestAnimationFrame(draw)
    }

    rafRef.current = requestAnimationFrame(draw)
  }

  const blobToDataUrl = async (blob: Blob): Promise<string> => {
    const arrayBuffer = await blob.arrayBuffer()
    const bytes = new Uint8Array(arrayBuffer)

    const chunkSize = 0x8000
    let binary = ''
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const slice = bytes.subarray(i, i + chunkSize)
      binary += String.fromCharCode(...slice)
    }
    const base64 = btoa(binary)
    const type = blob.type || 'application/octet-stream'
    return `data:${type};base64,${base64}`
  }

  const downloadRecording = () => {
    if (!finalBlob) return
    const url = URL.createObjectURL(finalBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = `recording_${new Date().toISOString().replace(/[:.]/g, '-')}.webm`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const start = async () => {
    if (disabled) return
    setError(null)
    setFinalBlob(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      let mimeType = ''
      if (typeof MediaRecorder !== 'undefined') {
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) mimeType = 'audio/webm;codecs=opus'
        else if (MediaRecorder.isTypeSupported('audio/webm')) mimeType = 'audio/webm'
      }

      let recorder: MediaRecorder
      try {
        recorder = mimeType ? new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 32000 }) : new MediaRecorder(stream, { audioBitsPerSecond: 32000 })
      } catch {
        recorder = new MediaRecorder(stream)
      }

      mediaRecorderRef.current = recorder
      finalSentRef.current = false
      chunksRef.current = []
      setElapsed(0)

      const audioContext = new AudioContext()
      audioContextRef.current = audioContext
      const source = audioContext.createMediaStreamSource(stream)
      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 2048
      analyserRef.current = analyser
      source.connect(analyser)

      recorder.ondataavailable = async (evt) => {
        if (!evt.data || evt.data.size === 0) return
        chunksRef.current.push(evt.data)
      }

      recorder.onstop = async () => {
        if (finalSentRef.current) return
        finalSentRef.current = true
        try {
          const finalBlob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
          setFinalBlob(finalBlob)
          const dataUrl = await blobToDataUrl(finalBlob)
          if (dataUrl.length > 45_000_000) {
            setError('录音过长导致数据过大，建议缩短录音时长后重试')
            onChunk({ base64: '', isFinal: true })
          } else {
            onChunk({ base64: dataUrl, isFinal: true })
          }
        } catch {
          onChunk({ base64: '', isFinal: true })
        }

        const stream = streamRef.current
        if (stream) {
          stream.getTracks().forEach((t) => t.stop())
          streamRef.current = null
        }

        const ctx = audioContextRef.current
        if (ctx) {
          try {
            await ctx.close()
          } catch {
            // ignore
          }
          audioContextRef.current = null
          analyserRef.current = null
        }
      }

      onStart?.()
      await new Promise((r) => setTimeout(r, 300))
      setIsRecording(true)
      drawWaveform()

      recorder.start(1000)
    } catch {
      setError('无法获取麦克风权限')
    }
  }

  const stop = async () => {
    const recorder = mediaRecorderRef.current
    if (!recorder) return
    setIsRecording(false)
    onStop?.()
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = null

    try {
      recorder.stop()
    } catch {
      if (!finalSentRef.current) {
        finalSentRef.current = true
        onChunk({ base64: '', isFinal: true })
      }
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-lg font-semibold mb-4">录音</h2>

      {error && <div className="text-red-600 text-sm mb-3">{error}</div>}
      <div className="text-xs text-gray-500 mb-3">建议在安静环境背诵，点击“完成”后会一次性提交完整录音。</div>
      {isRecording && isSilent && <div className="text-amber-600 text-sm mb-3">当前声音较小或环境过于安静，请靠近麦克风。</div>}

      <div className="flex items-center gap-3 mb-4">
        {!isRecording ? (
          <button
            onClick={start}
            disabled={disabled}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            开始背诵
          </button>
        ) : (
          <button onClick={stop} className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700">
            完成
          </button>
        )}
        <div className="text-sm text-gray-600">{timerLabel}</div>
      </div>

      <canvas ref={canvasRef} width={520} height={80} className="w-full bg-gray-50 rounded border" />

      <div className="mt-4">
        <button
          onClick={downloadRecording}
          disabled={!finalBlob}
          className="text-sm text-blue-600 hover:underline disabled:opacity-50"
        >
          下载本次录音
        </button>
      </div>
    </div>
  )
}
