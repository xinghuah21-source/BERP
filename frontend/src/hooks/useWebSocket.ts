import { useCallback, useEffect, useRef, useState } from 'react'

type WsStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

export interface WsPartialResult {
  type: 'partial_result'
  progress: number
  scores?: any
  transcript?: string
  error?: string
}

export interface WsState {
  type: 'state'
  task_text?: string
  progress?: number
}

export interface UseWebSocketOptions {
  userId: string
  token: string
  onMessage: (msg: WsPartialResult | WsState | any) => void
  onError?: (message: string) => void
}

function getWsBaseUrl() {
  const envBase = (import.meta as any).env?.VITE_WS_BASE_URL as string | undefined
  if (envBase && envBase.trim()) return envBase.trim().replace(/\/$/, '')

  const isViteDev = window.location.port === '5173'
  if (isViteDev) return 'ws://localhost:8002/ws'

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws`
}

export function useWebSocket({ userId, token, onMessage, onError }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const outboxRef = useRef<string[]>([])
  const closeByUserRef = useRef(false)
  const reconnectTimerRef = useRef<number | null>(null)
  const reconnectCountRef = useRef(0)
  const [status, setStatus] = useState<WsStatus>('idle')

  const connect = useCallback(() => {
    if (!token) {
      onError?.('缺少登录信息')
      return
    }
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return
    }

    setStatus('connecting')
    const base = getWsBaseUrl()
    const ws = new WebSocket(`${base}/${encodeURIComponent(userId)}?token=${encodeURIComponent(token)}`)
    wsRef.current = ws

    ws.onopen = () => {
      reconnectCountRef.current = 0
      setStatus('open')
      const outbox = outboxRef.current
      while (outbox.length > 0) {
        const msg = outbox.shift()
        if (msg) ws.send(msg)
      }
    }
    ws.onclose = () => {
      setStatus('closed')
      if (closeByUserRef.current) {
        closeByUserRef.current = false
        return
      }
      if (outboxRef.current.length > 0 && reconnectCountRef.current < 2) {
        reconnectCountRef.current += 1
        reconnectTimerRef.current = window.setTimeout(() => connect(), 800)
      }
      onError?.('连接已断开')
    }
    ws.onerror = () => {
      setStatus('error')
      onError?.('连接失败')
    }
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data as string)
        onMessage(msg)
      } catch {
        onError?.('消息解析失败')
      }
    }
  }, [onError, onMessage, token, userId])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (wsRef.current) {
      closeByUserRef.current = true
      wsRef.current.close()
      wsRef.current = null
    }
    setStatus('closed')
  }, [])

  const sendJson = useCallback((payload: any) => {
    const ws = wsRef.current
    const msg = JSON.stringify(payload)
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      outboxRef.current.push(msg)
      return
    }
    ws.send(msg)
  }, [])

  useEffect(() => {
    return () => {
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [])

  return { status, connect, disconnect, sendJson }
}
