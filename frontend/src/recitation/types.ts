﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿export type RecordingState = 'idle' | 'recording' | 'processing' | 'completed'

export interface ScoreBreakdown {
  accuracy: number
  pronunciation: number
  fluency: number
  semantic: number
}

export interface UserBaseline {
  baseline_arousal: number
  baseline_valence: number
  baseline_calibrated_at?: string | null
}

export interface RealtimeData {
  transcript: string
  progress: number
  stageText?: string
  scores: {
    total_score?: number
    breakdown?: Partial<ScoreBreakdown>
  }
  alerts: string[]
}

export interface EvaluationResult {
  total_score: number
  breakdown: ScoreBreakdown
  transcript: string
  standard_text: string
  feedback: string
  emotion_expression?: any
  intelligent_feedback?: any
  fallback_note?: string | null
  error_details?: Array<{
    type: string
    position: number
    expected: string
    actual: string
  }>
}
