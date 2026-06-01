import { create } from 'zustand'
import type { Task } from '../api/tasks'
import type { EvaluationResult, RecordingState, RealtimeData } from '../recitation/types'

interface ReciteState {
  currentTask: Task | null
  recordingState: RecordingState
  realtimeData: RealtimeData
  finalResult: EvaluationResult | null
  setTask: (task: Task) => void
  startRecording: () => void
  stopRecording: () => void
  setRealtimeData: (data: Partial<RealtimeData>) => void
  setFinalResult: (result: EvaluationResult) => void
  reset: () => void
}

const initialRealtime: RealtimeData = {
  transcript: '',
  progress: 0,
  stageText: '',
  scores: {},
  alerts: [],
}

export const useReciteStore = create<ReciteState>((set, get) => ({
  currentTask: null,
  recordingState: 'idle',
  realtimeData: initialRealtime,
  finalResult: null,

  setTask: (task) => set({ currentTask: task }),

  startRecording: () =>
    set({
      recordingState: 'recording',
      realtimeData: { ...initialRealtime },
      finalResult: null,
    }),

  stopRecording: () => {
    const state = get().recordingState
    if (state === 'recording') {
      set({ recordingState: 'processing' })
    }
  },

  setRealtimeData: (data) =>
    set((s) => ({
      realtimeData: {
        ...s.realtimeData,
        ...data,
        scores: { ...s.realtimeData.scores, ...data.scores },
      },
    })),

  setFinalResult: (result) =>
    set({
      finalResult: result,
      recordingState: 'completed',
      realtimeData: {
        transcript: result.transcript,
        progress: 100,
        stageText: '评测完成',
        scores: { total_score: result.total_score, breakdown: result.breakdown },
        alerts: result.feedback ? [result.feedback] : [],
      },
    }),

  reset: () =>
    set({
      currentTask: null,
      recordingState: 'idle',
      realtimeData: initialRealtime,
      finalResult: null,
    }),
}))
