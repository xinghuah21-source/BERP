import { apiClient } from './client'

export interface Task {
  id: string
  title: string
  content: string
  content_type: string
  difficulty?: 'easy' | 'medium' | 'hard'
  grade_level?: number
}

export interface CustomTask {
  id: string
  user_id: string
  title: string
  content: string
  language: 'zh' | 'en'
  content_type: 'poetry' | 'prose' | 'essay' | 'custom'
  created_at: string
  updated_at: string
}

export interface CustomTaskCreate {
  title: string
  content: string
  language: 'zh' | 'en'
  content_type?: 'poetry' | 'prose' | 'essay' | 'custom'
}

export interface CustomTaskUpdate {
  title?: string
  content?: string
  language?: 'zh' | 'en'
  content_type?: 'poetry' | 'prose' | 'essay' | 'custom'
}

export interface CustomTaskVoiceInputRequest {
  audio_base64: string
  language: 'zh' | 'en'
}

export interface CustomTaskVoiceInputResponse {
  transcript: string
}

export const tasksAPI = {
  getTasks: async (params?: { grade?: number; difficulty?: string }): Promise<Task[]> => {
    const response = await apiClient.get('/tasks', { params })
    return response.data
  },
  getTask: async (taskId: string): Promise<Task> => {
    try {
      const response = await apiClient.get(`/tasks/${taskId}`)
      return response.data
    } catch {
      const response = await apiClient.get(`/custom-tasks/${taskId}`)
      const t = response.data as any
      return {
        id: t.id,
        title: t.title,
        content: t.content,
        content_type: t.content_type || 'custom',
      }
    }
  },

  getMyCustomTasks: async (): Promise<CustomTask[]> => {
    const response = await apiClient.get('/custom-tasks')
    return response.data
  },

  createCustomTask: async (payload: CustomTaskCreate): Promise<CustomTask> => {
    const response = await apiClient.post('/custom-tasks', payload)
    return response.data
  },

  updateCustomTask: async (taskId: string, payload: CustomTaskUpdate): Promise<CustomTask> => {
    const response = await apiClient.put(`/custom-tasks/${taskId}`, payload)
    return response.data
  },

  deleteCustomTask: async (taskId: string): Promise<void> => {
    await apiClient.delete(`/custom-tasks/${taskId}`)
  },

  customTaskVoiceInput: async (payload: CustomTaskVoiceInputRequest): Promise<CustomTaskVoiceInputResponse> => {
    const response = await apiClient.post('/custom-tasks/voice-input', payload, { timeout: 90000 })
    return response.data
  },
}
