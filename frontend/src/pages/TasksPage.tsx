import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTaskStore } from '../stores/taskStore'
import { useAuthStore } from '../stores/authStore'
import Layout from '../components/Layout'
import Modal from '../components/Modal'
import ConfirmModal from '../components/ConfirmModal'
import AudioRecorder from '../components/recitation/AudioRecorder'
import { tasksAPI } from '../api/tasks'
import type { CustomTask } from '../api/tasks'

export default function TasksPage() {
  const navigate = useNavigate()
  const { tasks, customTasks, loading, error, fetchTasks, fetchMyCustomTasks, createCustomTask, updateCustomTask, deleteCustomTask } = useTaskStore()
  const { user, token, logout } = useAuthStore()
  const [tab, setTab] = useState<'system' | 'mine'>('system')

  const [showEditor, setShowEditor] = useState(false)
  const [editing, setEditing] = useState<CustomTask | null>(null)
  const [title, setTitle] = useState('')
  const [language, setLanguage] = useState<'zh' | 'en'>('zh')
  const [content, setContent] = useState('')
  const [contentType, setContentType] = useState<'poetry' | 'prose' | 'essay' | 'custom'>('custom')
  const [editorError, setEditorError] = useState<string | null>(null)

  const [deleteTarget, setDeleteTarget] = useState<CustomTask | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  const [showVoiceInput, setShowVoiceInput] = useState(false)
  const [voiceError, setVoiceError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    fetchTasks()
    fetchMyCustomTasks()
  }, [fetchMyCustomTasks, fetchTasks, navigate, token])

  const handleTaskClick = (taskId: string) => {
    navigate(`/recite/${taskId}`)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'easy': return 'bg-green-100 text-green-800'
      case 'medium': return 'bg-yellow-100 text-yellow-800'
      case 'hard': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const openCreate = () => {
    setEditing(null)
    setTitle('')
    setLanguage('zh')
    setContent('')
    setContentType('custom')
    setEditorError(null)
    setShowEditor(true)
  }

  const openEdit = (task: CustomTask) => {
    setEditing(task)
    setTitle(task.title)
    setLanguage(task.language)
    setContent(task.content)
    setContentType(task.content_type)
    setEditorError(null)
    setShowEditor(true)
  }

  const canSubmit = useMemo(() => title.trim().length > 0 && content.trim().length > 0, [content, title])

  const submit = async () => {
    if (!canSubmit) return
    setEditorError(null)
    if (!editing) {
      const created = await createCustomTask({ title: title.trim(), content: content.trim(), language, content_type: contentType })
      if (!created) {
        setEditorError('创建失败')
        return
      }
      setShowEditor(false)
      setTab('mine')
      return
    }
    const updated = await updateCustomTask(editing.id, { title: title.trim(), content: content.trim(), language, content_type: contentType })
    if (!updated) {
      setEditorError('保存失败')
      return
    }
    setShowEditor(false)
    setTab('mine')
  }

  const askDelete = (task: CustomTask) => {
    setDeleteTarget(task)
    setShowDeleteModal(true)
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    const ok = await deleteCustomTask(deleteTarget.id)
    if (ok) {
      setShowDeleteModal(false)
      setDeleteTarget(null)
    }
  }

  const voiceToText = async (audioDataUrl: string) => {
    setVoiceError(null)
    try {
      const json = await tasksAPI.customTaskVoiceInput({
        audio_base64: audioDataUrl,
        language: language === 'en' ? 'en' : 'zh',
      })
      const transcript = String(json?.transcript || '').trim()
      if (!transcript) {
        setVoiceError('识别失败，请手动输入或重试')
        return
      }
      setContent(transcript)
      setShowVoiceInput(false)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setVoiceError(typeof detail === 'string' && detail.trim() ? detail : '识别失败，请手动输入或重试')
    }
  }

  return (
    <Layout>
      <div className="mb-6 flex justify-between items-center">
        <h1 className="text-2xl font-bold">欢迎回来，{user?.username}</h1>
        <button
          onClick={handleLogout}
          className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700"
        >
          退出
        </button>
      </div>

      {loading ? (
        <div className="text-center py-8">加载中...</div>
      ) : (
        <>
          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              {error === '获取任务失败' ? '连接失败' : error}
            </div>
          )}
          <div className="mb-4 flex items-center justify-between">
            <div className="flex gap-2">
              <button
                onClick={() => setTab('system')}
                className={`px-3 py-2 rounded-md text-sm ${tab === 'system' ? 'bg-blue-600 text-white' : 'bg-white border hover:bg-gray-50'}`}
              >
                系统任务
              </button>
              <button
                onClick={() => setTab('mine')}
                className={`px-3 py-2 rounded-md text-sm ${tab === 'mine' ? 'bg-blue-600 text-white' : 'bg-white border hover:bg-gray-50'}`}
              >
                我的任务
              </button>
            </div>
            <button onClick={openCreate} className="px-3 py-2 rounded-md bg-green-600 text-white hover:bg-green-700">
              + 新建任务
            </button>
          </div>

          {tab === 'system' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  onClick={() => handleTaskClick(task.id)}
                  className="bg-white rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition-shadow"
                >
                  <h3 className="text-lg font-semibold mb-2">{task.title}</h3>
                  <div className="flex justify-between items-center mb-3">
                    <span className={`px-2 py-1 rounded-full text-xs ${getDifficultyColor(task.difficulty || 'easy')}`}>
                      {task.difficulty === 'easy' ? '简单' : task.difficulty === 'medium' ? '中等' : '困难'}
                    </span>
                    <span className="text-sm text-gray-600">年级: {task.grade_level ?? '-'}</span>
                  </div>
                  <p className="text-gray-700 text-sm line-clamp-3">{task.content}</p>
                  <div className="mt-4 text-xs text-gray-500">预计时长: 2-3分钟</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {customTasks.map((task) => (
                <div key={task.id} className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-semibold mb-2">{task.title}</h3>
                  <div className="flex items-center justify-between mb-3">
                    <span className="px-2 py-1 rounded-full text-xs bg-indigo-100 text-indigo-800">自建</span>
                    <span className="text-sm text-gray-600">{task.language === 'zh' ? '中文' : 'English'}</span>
                  </div>
                  <p className="text-gray-700 text-sm line-clamp-3">{task.content}</p>
                  <div className="mt-4 flex gap-3">
                    <button onClick={() => openEdit(task)} className="text-sm text-blue-600 hover:underline">
                      编辑
                    </button>
                    <button onClick={() => askDelete(task)} className="text-sm text-red-600 hover:underline">
                      删除
                    </button>
                    <button onClick={() => handleTaskClick(task.id)} className="ml-auto text-sm text-gray-700 hover:underline">
                      开始背诵
                    </button>
                  </div>
                </div>
              ))}
              {customTasks.length === 0 && <div className="text-gray-600">暂无自建任务</div>}
            </div>
          )}
        </>
      )}

      <Modal title={editing ? '编辑背诵任务' : '新建背诵任务'} open={showEditor} onClose={() => setShowEditor(false)}>
        <div className="space-y-4">
          {editorError && <div className="text-sm text-red-600">{editorError}</div>}
          <div>
            <div className="text-sm text-gray-600 mb-1">任务名称 *</div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full border rounded-md px-3 py-2"
              placeholder="静夜思 / My First Poem"
            />
          </div>
          <div>
            <div className="text-sm text-gray-600 mb-2">语言</div>
            <div className="flex gap-4">
              <label className="flex items-center gap-2">
                <input type="radio" checked={language === 'zh'} onChange={() => setLanguage('zh')} />
                中文
              </label>
              <label className="flex items-center gap-2">
                <input type="radio" checked={language === 'en'} onChange={() => setLanguage('en')} />
                English
              </label>
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600 mb-1">原文类型</div>
            <select value={contentType} onChange={(e) => setContentType(e.target.value as any)} className="w-full border rounded-md px-3 py-2">
              <option value="custom">自定义</option>
              <option value="poetry">诗歌</option>
              <option value="prose">散文</option>
              <option value="essay">短文</option>
            </select>
          </div>
          <div>
            <div className="text-sm text-gray-600 mb-1">背诵原文 *</div>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6} className="w-full border rounded-md px-3 py-2" />
            <div className="mt-2">
              <button onClick={() => setShowVoiceInput(true)} className="text-sm text-blue-600 hover:underline">
                🎤 语音输入原文
              </button>
            </div>
            <div className="text-xs text-gray-500 mt-1">识别失败时可手动输入或重试</div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setShowEditor(false)} className="px-4 py-2 rounded-md border hover:bg-gray-50">
              取消
            </button>
            <button
              onClick={submit}
              disabled={!canSubmit}
              className="px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {editing ? '确认保存' : '确认创建'}
            </button>
          </div>
        </div>
      </Modal>

      <Modal title="语音输入原文" open={showVoiceInput} onClose={() => setShowVoiceInput(false)}>
        <div className="space-y-3">
          <div className="text-sm text-gray-600">请准确朗读您要添加的原文，系统将自动识别</div>
          {voiceError && <div className="text-sm text-red-600">{voiceError}</div>}
          <AudioRecorder
            estimatedSeconds={15}
            onChunk={(p) => {
              if (!p.isFinal) return
              void voiceToText(p.base64)
            }}
          />
        </div>
      </Modal>

      <ConfirmModal
        open={showDeleteModal}
        title="确认删除"
        message={deleteTarget ? `您确定要删除任务\"${deleteTarget.title}\"吗？` : '确认删除该任务吗？'}
        detail="删除后无法恢复，该任务下的所有背诵记录也将被清除。"
        onClose={() => setShowDeleteModal(false)}
        onConfirm={confirmDelete}
      />
    </Layout>
  )
}
