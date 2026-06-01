import { create } from 'zustand'
import { tasksAPI, Task, type CustomTask, type CustomTaskCreate, type CustomTaskUpdate } from '../api/tasks'

interface TaskState {
  tasks: Task[]
  customTasks: CustomTask[]
  loading: boolean
  error: string | null
  fetchTasks: (params?: { grade?: number; difficulty?: string }) => Promise<void>
  fetchMyCustomTasks: () => Promise<void>
  createCustomTask: (payload: CustomTaskCreate) => Promise<CustomTask | null>
  updateCustomTask: (taskId: string, payload: CustomTaskUpdate) => Promise<CustomTask | null>
  deleteCustomTask: (taskId: string) => Promise<boolean>
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  customTasks: [],
  loading: false,
  error: null,
  
  fetchTasks: async (params) => {
    set({ loading: true, error: null })
    try {
      const tasks = await tasksAPI.getTasks(params)
      set({ tasks, loading: false })
    } catch (error) {
      set({ error: '获取任务失败', loading: false })
    }
  },

  fetchMyCustomTasks: async () => {
    set({ loading: true, error: null })
    try {
      const customTasks = await tasksAPI.getMyCustomTasks()
      set({ customTasks, loading: false })
    } catch {
      set({ error: '获取任务失败', loading: false })
    }
  },

  createCustomTask: async (payload) => {
    set({ loading: true, error: null })
    try {
      const created = await tasksAPI.createCustomTask(payload)
      set((s) => ({ customTasks: [created, ...s.customTasks], loading: false }))
      return created
    } catch {
      set({ error: '创建失败', loading: false })
      return null
    }
  },

  updateCustomTask: async (taskId, payload) => {
    set({ loading: true, error: null })
    try {
      const updated = await tasksAPI.updateCustomTask(taskId, payload)
      set((s) => ({
        customTasks: s.customTasks.map((t) => (t.id === taskId ? updated : t)),
        loading: false,
      }))
      return updated
    } catch {
      set({ error: '保存失败', loading: false })
      return null
    }
  },

  deleteCustomTask: async (taskId) => {
    set({ loading: true, error: null })
    try {
      await tasksAPI.deleteCustomTask(taskId)
      set((s) => ({ customTasks: s.customTasks.filter((t) => t.id !== taskId), loading: false }))
      return true
    } catch {
      set({ error: '删除失败', loading: false })
      return false
    }
  },
}))
