import { useState, useEffect, useRef, useCallback } from 'react'

export default function useWebSocket(url) {
  const [lastMessage, setLastMessage] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const ws = useRef(null)
  const reconnectTimeout = useRef(null)
  const reconnectAttempts = useRef(0)

  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(url)

      ws.current.onopen = () => {
        setIsConnected(true)
        reconnectAttempts.current = 0
        console.log('[WS] Connected')
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setLastMessage(data)
        } catch (e) {
          // ignore non-JSON
        }
      }

      ws.current.onclose = () => {
        setIsConnected(false)
        console.log('[WS] Disconnected, reconnecting...')
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000)
        reconnectAttempts.current++
        reconnectTimeout.current = setTimeout(connect, delay)
      }

      ws.current.onerror = (err) => {
        console.error('[WS] Error', err)
        ws.current.close()
      }
    } catch (e) {
      const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000)
      reconnectAttempts.current++
      reconnectTimeout.current = setTimeout(connect, delay)
    }
  }, [url])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimeout.current)
      if (ws.current) ws.current.close()
    }
  }, [connect])

  return { lastMessage, isConnected }
}
