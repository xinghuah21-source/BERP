import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI } from '../api/auth'
import { useAuthStore } from '../stores/authStore'
import Layout from '../components/Layout'

export default function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [grade, setGrade] = useState('1')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { login } = useAuthStore()

  const validationError = useMemo(() => {
    const trimmedUsername = username.trim()
    if (!trimmedUsername) return '请输入用户名'
    if (trimmedUsername.length < 3) return '用户名至少 3 个字符'
    if (trimmedUsername.length > 20) return '用户名不能超过 20 个字符'
    if (!/^[a-zA-Z0-9_]+$/.test(trimmedUsername)) return '用户名仅支持字母、数字和下划线'
    if (!password) return '请输入密码'
    if (password.length < 6) return '密码至少 6 位'
    if (mode === 'register') {
      if (confirmPassword !== password) return '两次输入的密码不一致'
      const gradeNum = Number(grade)
      if (!Number.isInteger(gradeNum) || gradeNum < 1 || gradeNum > 12) return '年级需在 1 到 12 之间'
    }
    return ''
  }, [confirmPassword, grade, mode, password, username])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (validationError) {
      setError(validationError)
      return
    }
    setLoading(true)

    try {
      const trimmedUsername = username.trim()
      const response = mode === 'login'
        ? await authAPI.login({ username: trimmedUsername, password })
        : await authAPI.register({ username: trimmedUsername, password, role: 'student', grade: Number(grade) })
      const profile = await authAPI.me(response.access_token)
      login(response.access_token, profile)
      if (mode === 'register') setSuccess('注册成功，已自动登录。')
      navigate('/tasks')
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      if (typeof detail === 'string' && detail.trim()) {
        setError(mode === 'login' ? `登录失败：${detail}` : `注册失败：${detail}`)
      } else {
        setError(mode === 'login' ? '登录失败' : '注册失败')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-20">
        <div className="bg-white rounded-lg shadow-md p-8">
          <h1 className="text-2xl font-bold text-center mb-6">BERP 背诵平台</h1>
          <div className="grid grid-cols-2 gap-2 mb-6 bg-gray-100 rounded-md p-1">
            <button
              type="button"
              onClick={() => {
                setMode('login')
                setError('')
                setSuccess('')
              }}
              className={`py-2 rounded-md text-sm font-medium ${mode === 'login' ? 'bg-white shadow text-blue-600' : 'text-gray-600'}`}
            >
              登录
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('register')
                setError('')
                setSuccess('')
              }}
              className={`py-2 rounded-md text-sm font-medium ${mode === 'register' ? 'bg-white shadow text-blue-600' : 'text-gray-600'}`}
            >
              注册
            </button>
          </div>

          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          {success && (
            <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
                用户名
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                密码
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            {mode === 'register' && (
              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                  确认密码
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
            )}

            {mode === 'register' && (
              <div>
                <label htmlFor="grade" className="block text-sm font-medium text-gray-700 mb-1">
                  年级
                </label>
                <input
                  id="grade"
                  type="number"
                  min={1}
                  max={12}
                  value={grade}
                  onChange={(e) => setGrade(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
            )}

            {mode === 'register' && (
              <div className="text-xs text-gray-500">
                用户名支持字母、数字和下划线；密码至少 6 位；年级范围 1-12。
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            >
              {loading ? (mode === 'login' ? '登录中...' : '注册中...') : (mode === 'login' ? '登录' : '注册并进入系统')}
            </button>
          </form>
        </div>
      </div>
    </Layout>
  )
}
