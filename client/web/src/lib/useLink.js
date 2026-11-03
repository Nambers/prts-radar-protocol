import { useCallback, useEffect, useRef, useState } from 'react'

const WS_URL = () =>
  `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

let seq = 0

export function useLink() {
  const [state, setState] = useState({ kind: 'real', phase: 'idle', address: null,
    name: null, mtu: null, chrcCount: 0, adapter: null })
  const [entries, setEntries] = useState([])
  const [scan, setScan] = useState(null)
  const [online, setOnline] = useState(false)
  const wsRef = useRef(null)
  const retryRef = useRef(0)

  const push = useCallback((e) => {
    setEntries((prev) => [...prev.slice(-399), { id: ++seq, ...e }])
  }, [])

  useEffect(() => {
    let closed = false
    let timer

    const open = () => {
      const ws = new WebSocket(WS_URL())
      wsRef.current = ws
      ws.onopen = () => { retryRef.current = 0; setOnline(true); ws.send(JSON.stringify({ op: 'hello' })) }
      ws.onclose = () => {
        setOnline(false)
        if (closed) return
        const wait = Math.min(4000, 400 * 2 ** retryRef.current++)
        timer = setTimeout(open, wait)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (ev) => {
        const m = JSON.parse(ev.data)
        if (m.type === 'state') setState((s) => ({ ...s, ...m }))
        else if (m.type === 'scan') setScan(m.devices)
        else push(m)
      }
    }
    open()
    return () => { closed = true; clearTimeout(timer); wsRef.current?.close() }
  }, [push])

  const send = useCallback((msg) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== 1) {
      push({ type: 'error', at: Date.now() / 1000, text: '后端未连接 —— 检查 uvicorn 是否在 8787 上跑着' })
      return
    }
    ws.send(JSON.stringify(msg))
  }, [push])

  return { state, entries, scan, online, send, setScan,
    clear: () => setEntries([]) }
}
