﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import TextDisplay from '../components/recitation/TextDisplay'
import AudioRecorder from '../components/recitation/AudioRecorder'
import ResultView from '../components/recitation/ResultView'
import { tasksAPI } from '../api/tasks'
import { authAPI } from '../api/auth'
import { useAuthStore } from '../stores/authStore'
import { useReciteStore } from '../stores/reciteStore'
import type { EvaluationResult, UserBaseline } from '../recitation/types'
import { useWebSocket } from '../hooks/useWebSocket'

const CALIBRATION_SAMPLE_TEXT = '今天是晴天。小树站在操场边，叶子轻轻摇动。远处传来读书声，同学们安静地走进教室，开始新一天的学习。'

export default function RecitePage() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const { token, user, setUser } = useAuthStore()
  const {
    currentTask,
    recordingState,
    realtimeData,
    finalResult,
    setTask,
    startRecording,
    stopRecording,
    setRealtimeData,
    setFinalResult,
    reset,
  } = useReciteStore()

  const [loadError, setLoadError] = useState<string | null>(null)
  const processingTimerRef = useRef<number | null>(null)
  const [showOriginal, setShowOriginal] = useState(true)
  const [isCalibrating, setIsCalibrating] = useState(false)
  const [calibrationNotice, setCalibrationNotice] = useState<string | null>(null)
  const [calibrationBaseline, setCalibrationBaseline] = useState<UserBaseline | null>(null)
  const [skipCalibration, setSkipCalibration] = useState(false)
  const [ttsSupported, setTtsSupported] = useState(false)
  const [speakingKey, setSpeakingKey] = useState<string | null>(null)
  const [showCalibrationPanel, setShowCalibrationPanel] = useState(false)

  const userId = useMemo(() => user?.username || 'guest', [user?.username])
  const skipKey = useMemo(() => (user?.username ? `berp_skip_calibration_${user.username}` : null), [user?.username])
  const needsCalibration = useMemo(() => Boolean(user && !user.is_baseline_calibrated && !skipCalibration), [skipCalibration, user])

  useEffect(() => {
    setTtsSupported(typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window)
  }, [])

  useEffect(() => {
    if (!skipKey) {
      setSkipCalibration(false)
      return
    }
    setSkipCalibration(localStorage.getItem(skipKey) === '1')
  }, [skipKey])

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const speakText = useCallback((text: string, key: string) => {
    if (!ttsSupported || !text.trim()) return
    const synth = window.speechSynthesis
    if (speakingKey === key) {
      synth.cancel()
      setSpeakingKey(null)
      return
    }

    synth.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'zh-CN'
    utterance.rate = 0.92
    utterance.pitch = 1

    const voices = synth.getVoices()
    const preferredVoice = voices.find((v) => /zh|Chinese/i.test(v.lang) && /Microsoft|Xiaoxiao|Yunxi|Xiaoyi/i.test(v.name))
      || voices.find((v) => /zh|Chinese/i.test(v.lang))
    if (preferredVoice) utterance.voice = preferredVoice

    utterance.onend = () => setSpeakingKey((prev) => (prev === key ? null : prev))
    utterance.onerror = () => setSpeakingKey((prev) => (prev === key ? null : prev))

    setSpeakingKey(key)
    synth.speak(utterance)
  }, [speakingKey, ttsSupported])

  const handleSkipCalibration = useCallback(() => {
    if (!skipKey) return
    localStorage.setItem(skipKey, '1')
    setSkipCalibration(true)
    setCalibrationNotice('已跳过校准，本次评测将使用默认情感匹配逻辑。')
  }, [skipKey])

  const handleEnableCalibrationAgain = useCallback(() => {
    if (!skipKey) return
    localStorage.removeItem(skipKey)
    setSkipCalibration(false)
    setCalibrationNotice('已恢复校准提示，你可以随时进行声音校准。')
  }, [skipKey])

  const handleWsMessage = useCallback(
    (msg: any) => {
      if (msg?.type === 'state') {
        const patch: any = {}
        if (typeof msg.progress === 'number') {
          patch.progress = msg.progress
        }
        if (typeof msg.stage_text === 'string') {
          patch.stageText = msg.stage_text
        }
        if (typeof msg.task_text === 'string') {
          patch.alerts = []
        }
        if (Object.keys(patch).length > 0) setRealtimeData(patch)
        return
      }

      if (msg?.type === 'partial_result') {
        const progress = typeof msg.progress === 'number' ? msg.progress : 0
        const transcript = typeof msg.transcript === 'string' ? msg.transcript : ''
        const breakdown = msg.scores?.breakdown || {}
        const total_score = msg.scores?.total_score
        const emotion_expression = msg.emotion_expression
        const intelligent_feedback = msg.intelligent_feedback
        const fallback_note = msg.fallback_note

        const alerts: string[] = []
        if (typeof msg.error === 'string' && msg.error) alerts.push(msg.error)
        if (typeof msg.feedback === 'string' && msg.feedback) alerts.push(msg.feedback)
        if (typeof fallback_note === 'string' && fallback_note) alerts.push(fallback_note)

        setRealtimeData({
          progress,
          stageText: typeof msg.stage_text === 'string' ? msg.stage_text : progress >= 100 ? '评测完成' : realtimeData.stageText,
          transcript,
          scores: { total_score, breakdown },
          alerts,
        })

        if (progress >= 100 && currentTask) {
          setShowOriginal(true)
          const result: EvaluationResult = {
            total_score: Number(total_score ?? 0),
            breakdown: {
              accuracy: Number(breakdown.accuracy ?? 0),
              pronunciation: Number(breakdown.pronunciation ?? 0),
              fluency: Number(breakdown.fluency ?? 0),
              semantic: Number(breakdown.semantic ?? 0),
            },
            transcript,
            standard_text: currentTask.content,
            feedback: alerts[0] || '评测完成',
            emotion_expression,
            intelligent_feedback,
            fallback_note,
            error_details: Array.isArray(msg.error_details) ? msg.error_details : undefined,
          }
          setFinalResult(result)
        }
      }
    },
    [currentTask, realtimeData.stageText, setFinalResult, setRealtimeData]
  )

  const { status: wsStatus, connect: wsConnect, disconnect: wsDisconnect, sendJson } = useWebSocket({
    userId,
    token: token || '',
    onMessage: handleWsMessage,
    onError: (m) => setRealtimeData({ alerts: [m] }),
  })

  useEffect(() => {
    if (!token || !currentTask) return
    wsConnect()
    sendJson({ type: 'set_task', standard_text: currentTask.content })
  }, [currentTask, sendJson, token, wsConnect])

  useEffect(() => {
    if (recordingState !== 'processing' || !currentTask) return
    if (processingTimerRef.current) window.clearTimeout(processingTimerRef.current)
    processingTimerRef.current = window.setTimeout(() => {
      setRealtimeData({ alerts: ['服务繁忙，请重试'], stageText: '评测超时' })
      const result: EvaluationResult = {
        total_score: Number(realtimeData.scores?.total_score ?? 0),
        breakdown: {
          accuracy: Number((realtimeData.scores as any)?.breakdown?.accuracy ?? 0),
          pronunciation: Number((realtimeData.scores as any)?.breakdown?.pronunciation ?? 0),
          fluency: Number((realtimeData.scores as any)?.breakdown?.fluency ?? 0),
          semantic: Number((realtimeData.scores as any)?.breakdown?.semantic ?? 0),
        },
        transcript: realtimeData.transcript || '',
        standard_text: currentTask.content,
        feedback: '服务繁忙，请重试',
      }
      setFinalResult(result)
    }, 90000)
    return () => {
      if (processingTimerRef.current) {
        window.clearTimeout(processingTimerRef.current)
        processingTimerRef.current = null
      }
    }
  }, [currentTask, recordingState, realtimeData.progress, realtimeData.scores, realtimeData.stageText, realtimeData.transcript, setFinalResult, setRealtimeData])

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    if (!taskId) return

    let mounted = true
    setLoadError(null)
    tasksAPI
      .getTask(taskId)
      .then((t) => {
        if (!mounted) return
        setTask(t)
      })
      .catch(() => {
        if (!mounted) return
        setLoadError('连接失败')
      })

    return () => {
      mounted = false
    }
  }, [navigate, setTask, taskId, token])

  useEffect(() => {
    return () => {
      wsDisconnect()
      reset()
    }
  }, [reset, wsDisconnect])

  useEffect(() => {
    if (!user) return
    if (user.is_baseline_calibrated && user.baseline_arousal != null && user.baseline_valence != null) {
      setCalibrationBaseline({
        baseline_arousal: user.baseline_arousal,
        baseline_valence: user.baseline_valence,
        baseline_calibrated_at: user.baseline_calibrated_at,
      })
      setShowCalibrationPanel(false)
    } else if (!user.is_baseline_calibrated && !skipCalibration) {
      setShowCalibrationPanel(true)
    }
  }, [skipCalibration, user])

  const refreshProfile = useCallback(async () => {
    const profile = await authAPI.me()
    setUser(profile)
    if (profile.is_baseline_calibrated && profile.baseline_arousal != null && profile.baseline_valence != null) {
      setCalibrationBaseline({
        baseline_arousal: profile.baseline_arousal,
        baseline_valence: profile.baseline_valence,
        baseline_calibrated_at: profile.baseline_calibrated_at,
      })
      if (skipKey) localStorage.removeItem(skipKey)
      setSkipCalibration(false)
    }
  }, [setUser, skipKey])

  const onStart = () => {
    if (!currentTask) return
    setShowOriginal(false)
    startRecording()
    wsConnect()
    sendJson({
      type: 'set_task',
      standard_text: currentTask.content,
      user_baseline: calibrationBaseline,
    })
  }

  const onStop = () => {
    stopRecording()
    setShowOriginal(true)
  }

  const onChunk = (payload: { base64: string; isFinal: boolean }) => {
    if (wsStatus !== 'open') wsConnect()
    sendJson({ type: 'audio_chunk', data: payload.base64, seq: 1, is_final: payload.isFinal, user_baseline: calibrationBaseline })
  }

  const fileToDataUrl = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onerror = () => reject(new Error('读取文件失败'))
      reader.onload = () => resolve(String(reader.result))
      reader.readAsDataURL(file)
    })

  const onPickFile = async (evt: ChangeEvent<HTMLInputElement>) => {
    const f = evt.target.files?.[0]
    evt.target.value = ''
    if (!f || !currentTask) return
    startRecording()
    wsConnect()
    sendJson({ type: 'set_task', standard_text: currentTask.content, user_baseline: calibrationBaseline })
    try {
      const dataUrl = await fileToDataUrl(f)
      sendJson({ type: 'audio_chunk', data: dataUrl, seq: 1, is_final: true, user_baseline: calibrationBaseline })
      stopRecording()
    } catch {
      setRealtimeData({ alerts: ['文件读取失败'] })
      stopRecording()
    }
  }

  const onRetry = () => {
    reset()
    navigate('/tasks')
  }

  const handleCalibrationChunk = async (payload: { base64: string; isFinal: boolean }) => {
    if (!payload.isFinal || !payload.base64) return
    await submitCalibrationAudio(payload.base64)
  }

  const submitCalibrationAudio = useCallback(async (audioBase64: string) => {
    setCalibrationNotice(null)
    setIsCalibrating(true)
    try {
      const resp = await authAPI.calibrateBaseline({
        audio_base64: audioBase64,
        sample_text: CALIBRATION_SAMPLE_TEXT,
        language: 'zh',
      })
      setCalibrationBaseline({
        baseline_arousal: Number(resp.baseline_arousal ?? 0),
        baseline_valence: Number(resp.baseline_valence ?? 0),
        baseline_calibrated_at: resp.baseline_calibrated_at,
      })
      await refreshProfile()
      setCalibrationNotice('校准完成，接下来可以开始正式背诵。')
      setShowCalibrationPanel(false)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setCalibrationNotice(typeof detail === 'string' && detail.trim() ? detail : '校准失败，请重新朗读一次中性短文。')
    } finally {
      setIsCalibrating(false)
    }
  }, [refreshProfile])

  const onPickCalibrationFile = async (evt: ChangeEvent<HTMLInputElement>) => {
    const f = evt.target.files?.[0]
    evt.target.value = ''
    if (!f) return
    try {
      const dataUrl = await fileToDataUrl(f)
      await submitCalibrationAudio(dataUrl)
    } catch {
      setCalibrationNotice('校准音频读取失败，请重新选择文件。')
    }
  }

  return (
    <Layout>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">背诵</h1>
        <button onClick={() => navigate('/tasks')} className="text-sm text-blue-600 hover:underline">
          返回任务列表
        </button>
      </div>

      {loadError && <div className="text-red-600 mb-4">{loadError}</div>}
      {!currentTask ? (
        <div className="text-center py-12 text-gray-600">加载任务中...</div>
      ) : finalResult ? (
        <ResultView result={finalResult} onRetry={onRetry} />
      ) : (
        <div className="space-y-6">
          {user && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <div className="flex items-center justify-between gap-4 mb-2">
                <div className="text-lg font-semibold text-blue-900">声音校准</div>
                <div className="flex gap-3">
                  {ttsSupported && (
                    <button
                      onClick={() => speakText(CALIBRATION_SAMPLE_TEXT, 'calibration')}
                      className="text-sm text-blue-700 hover:underline"
                    >
                      {speakingKey === 'calibration' ? '停止校准示例' : '播放校准示例'}
                    </button>
                  )}
                  {needsCalibration ? (
                    <button onClick={handleSkipCalibration} className="text-sm text-gray-700 hover:underline">
                      跳过校准
                    </button>
                  ) : (
                    <button
                      onClick={() => setShowCalibrationPanel((prev) => !prev)}
                      className="text-sm text-blue-700 hover:underline"
                    >
                      {showCalibrationPanel ? '收起重新校准' : '重新校准'}
                    </button>
                  )}
                  {!needsCalibration && skipCalibration && (
                    <button onClick={handleEnableCalibrationAgain} className="text-sm text-blue-700 hover:underline">
                      重新启用校准
                    </button>
                  )}
                </div>
              </div>
              <div className="text-sm text-blue-800 mb-3">
                {needsCalibration
                  ? '首次使用前，可先朗读下面这段中性短文，系统会记录你的个人情感基线；如果暂时不想校准，也可以直接跳过并使用默认匹配逻辑。'
                  : '你可以随时重新朗读下面这段中性短文，覆盖当前个人情感基线。'}
              </div>
              {!needsCalibration && calibrationBaseline && (
                <div className="bg-white border rounded-md p-4 text-sm text-gray-700 mb-4">
                  当前已存在个人情感基线，如重新校准，将用新的结果覆盖原基线。
                </div>
              )}
              {(needsCalibration || showCalibrationPanel) && (
                <div className="bg-white border rounded-md p-4 text-gray-800 leading-7 mb-4">{CALIBRATION_SAMPLE_TEXT}</div>
              )}
              {calibrationNotice && <div className="text-sm text-blue-700 mb-3">{calibrationNotice}</div>}
              {(needsCalibration || showCalibrationPanel) && (
                <div className="space-y-4">
                  <AudioRecorder disabled={isCalibrating} estimatedSeconds={20} onChunk={handleCalibrationChunk} />
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-700 mb-2">也可以直接上传一段朗读该中性短文的音频文件完成校准。</div>
                    <input
                      type="file"
                      accept="audio/*"
                      disabled={isCalibrating}
                      onChange={onPickCalibrationFile}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {!needsCalibration && calibrationBaseline && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
              已完成声音校准，本次评测将使用个人基线进行情感匹配。
            </div>
          )}

          {!needsCalibration && user && !user.is_baseline_calibrated && !calibrationBaseline && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
              你已跳过校准，本次评测将使用默认情感匹配逻辑。
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <div className="mb-4 bg-white rounded-lg shadow-md p-6">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm text-gray-600 mb-1">任务</div>
                    <div className="text-lg font-semibold">{currentTask.title}</div>
                  </div>
                  {ttsSupported && (
                    <button onClick={() => speakText(currentTask.content, 'poem')} className="text-sm text-blue-600 hover:underline">
                      {speakingKey === 'poem' ? '停止原文示例' : '播放原文示例'}
                    </button>
                  )}
                </div>
              </div>
              <div
                className={`transition-all duration-500 ${
                  showOriginal ? 'opacity-100 max-h-[480px]' : 'opacity-0 max-h-0 overflow-hidden'
                }`}
              >
                <TextDisplay standardText={currentTask.content} currentProgress={realtimeData.progress} />
              </div>
              {!showOriginal && (
                <div className="mt-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-4 py-3">
                  请凭记忆背诵，原文已隐藏
                </div>
              )}
            </div>

            <div className="space-y-6">
              <AudioRecorder
                disabled={!token || wsStatus === 'connecting' || recordingState === 'processing'}
                onStart={onStart}
                onStop={onStop}
                onChunk={onChunk}
              />

              <div className="bg-white rounded-lg shadow-md p-6">
                <input
                  type="file"
                  accept="audio/*"
                  disabled={!token || wsStatus === 'connecting' || recordingState === 'processing'}
                  onChange={onPickFile}
                />
              </div>

              {recordingState === 'processing' && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-4">
                  <div className="flex items-center justify-between text-sm font-medium text-yellow-900 mb-2">
                    <span>{realtimeData.stageText || '实时评测进度'}</span>
                    <span>{Math.max(0, Math.min(100, Math.round(realtimeData.progress || 0)))}%</span>
                  </div>
                  <div className="w-full h-3 bg-yellow-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-yellow-500 transition-all duration-300"
                      style={{ width: `${Math.max(0, Math.min(100, realtimeData.progress || 0))}%` }}
                    />
                  </div>
                  <div className="mt-2 text-sm text-yellow-800">
                    {realtimeData.transcript ? `当前识别文本：${realtimeData.transcript}` : '音频已提交，系统正在按阶段处理，请稍候。'}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
