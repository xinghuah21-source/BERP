import { apiClient } from './client'

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface UserProfile {
  id: string
  username: string
  role: string
  grade: number
  is_baseline_calibrated: boolean
  baseline_arousal?: number | null
  baseline_valence?: number | null
  baseline_calibrated_at?: string | null
}

export interface BaselineResponse {
  is_calibrated: boolean
  baseline_arousal?: number | null
  baseline_valence?: number | null
  baseline_calibrated_at?: string | null
}

export interface CalibrateBaselineRequest {
  audio_base64: string
  sample_text: string
  language?: string
}

export interface CalibrateBaselineResponse extends BaselineResponse {
  sample_text: string
  audio_quality?: Record<string, unknown> | null
}

export const authAPI = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post('/auth/login', data)
    return response.data
  },

  register: async (data: LoginRequest & { role: string; grade: number }): Promise<LoginResponse> => {
    const response = await apiClient.post('/auth/register', data)
    return response.data
  },

  me: async (token?: string): Promise<UserProfile> => {
    const response = await apiClient.get('/auth/me', token ? {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    } : undefined)
    return response.data
  },

  getBaseline: async (): Promise<BaselineResponse> => {
    const response = await apiClient.get('/auth/baseline')
    return response.data
  },

  calibrateBaseline: async (data: CalibrateBaselineRequest): Promise<CalibrateBaselineResponse> => {
    const response = await apiClient.post('/auth/baseline/calibrate', data, { timeout: 90000 })
    return response.data
  },
}
