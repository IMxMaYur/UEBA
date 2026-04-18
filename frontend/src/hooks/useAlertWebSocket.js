/**
 * useAlertWebSocket.js
 * 
 * React hook for real-time alert notifications via WebSocket.
 * Connects to the UEBA backend's /ws/alerts endpoint and
 * exposes the latest incoming alert + unread count.
 * 
 * Automatically reconnects on disconnect (exponential backoff).
 * Works across both localhost and 2-laptop demo configurations.
 */

import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = (() => {
  const host = window.location.hostname
  const port = import.meta.env.VITE_API_PORT || '8000'
  return `ws://${host}:${port}/ws/alerts`
})()

export function useAlertWebSocket() {
  const [latestAlert, setLatestAlert] = useState(null)
  const [alertQueue, setAlertQueue] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [isConnected, setIsConnected] = useState(false)

  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const reconnectDelay = useRef(1000)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        setIsConnected(true)
        reconnectDelay.current = 1000
        // Keep-alive ping every 30s
        ws._pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping')
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        if (event.data === 'pong') return
        try {
          const data = JSON.parse(event.data)
          if (data.event === 'NEW_ALERT') {
            setLatestAlert(data)
            setAlertQueue(prev => [data, ...prev].slice(0, 50))  // keep last 50
            setUnreadCount(prev => prev + 1)
          }
        } catch (_) {}
      }

      ws.onclose = () => {
        clearInterval(ws._pingInterval)
        setIsConnected(false)
        // Reconnect with backoff (max 30s)
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
          connect()
        }, reconnectDelay.current)
      }

      ws.onerror = () => {
        ws.close()
      }

      wsRef.current = ws
    } catch (_) {}
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  const clearUnread = useCallback(() => setUnreadCount(0), [])
  const clearQueue = useCallback(() => setAlertQueue([]), [])

  return {
    latestAlert,
    alertQueue,
    unreadCount,
    isConnected,
    clearUnread,
    clearQueue,
  }
}
