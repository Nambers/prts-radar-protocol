import { useCallback, useRef, useState } from 'react'
import { buildFrame } from './frame.js'
import { parseReply, versionFromReply } from './parse.js'
import { catalogFor } from './catalog.js'

const SVC = 0xfef0
const NOTIFY = 0xfef1
const WRITE = 0xfef2

const specFor = (fw, name) => catalogFor(fw).commands.find((c) => c.name === name) || null
const supported = () => typeof navigator !== 'undefined' && !!navigator.bluetooth
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function withTimeout(promise, ms, msg) {
  let t
  const timeout = new Promise((_, rej) => { t = setTimeout(() => rej(new Error(msg)), ms) })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(t))
}

export const CONNECT_LIMIT_S = 30
export const DISCOVER_LIMIT_S = 70

// Linux 上 connect() 在链路建好时就返回，GATT 发现（30–60 s）在 getPrimaryService 里等
async function openService(device, uuid, onFail, tries = 2) {
  let last
  for (let i = 0; i < tries; i++) {
    const t0 = Date.now()
    try {
      await withTimeout(device.gatt.connect(), CONNECT_LIMIT_S * 1000, `建链超时（${CONNECT_LIMIT_S}s）`)
      await sleep(250)
      if (!device.gatt.connected) throw new Error('连上后又立刻掉线')
      return await withTimeout(device.gatt.getPrimaryService(uuid), DISCOVER_LIMIT_S * 1000,
        `GATT 发现超时（${DISCOVER_LIMIT_S}s）`)
    } catch (e) {
      last = e
      onFail(`第 ${i + 1}/${tries} 次连接失败（${Math.round((Date.now() - t0) / 1000)}s）：${e?.message || e}`)
      try { device.gatt.disconnect() } catch {  }
      if (e?.name === 'NotFoundError') break
      await sleep(400)
    }
  }
  throw last
}

let seq = 0

export function useBleLink() {
  const [state, setState] = useState({
    kind: 'real', phase: 'idle', address: null, name: null,
    mtu: null, mtuFloor: null, mtuEffective: null, chrcCount: 0,
    adapter: 'Web Bluetooth', fw: null, phaseSince: null, phaseLimit: null,
  })
  const [entries, setEntries] = useState([])
  const [scan, setScan] = useState(null)
  const [online] = useState(supported())

  const fwRef = useRef(null)
  const dev = useRef({ device: null, write: null, notify: null, floor: 0, txAt: null, txCmd: null, pageUntil: 0 })

  const push = useCallback((e) => setEntries((prev) => [...prev.slice(-399), { id: ++seq, ...e }]), [])
  const patch = useCallback((p) => setState((s) => ({ ...s, ...p })), [])
  const toPhase = useCallback((phase, extra = {}) => setState((s) => ({
    ...s, phase, phaseSince: Date.now() / 1000, ...extra,
  })), [])
  const err = useCallback((text, kind) => push({ type: 'error', at: Date.now() / 1000, text, ...(kind ? { kind } : {}) }), [push])
  const log = useCallback((level, text) => push({ type: 'log', level, at: Date.now() / 1000, text }), [push])

  const onNotify = useCallback((ev) => {
    const data = new Uint8Array(ev.target.value.buffer)
    const now = Date.now() / 1000
    const d = dev.current
    const rtt = d.txAt != null ? Math.round((now - d.txAt) * 1000) : null
    const floor = data.length + 3
    if (floor > d.floor) { d.floor = floor; patch({ mtuFloor: floor, mtuEffective: floor }) }
    const spec = d.txCmd ? specFor(fwRef.current, d.txCmd) : null
    const parsed = parseReply(data, { spec, tplHex: spec?.reply?.tpl || null, mtu: d.floor, paging: now < d.pageUntil })
    push({ type: 'rx', at: now, rtt, forCmd: d.txCmd, ...parsed })
    const v = versionFromReply(data)
    if (v) { fwRef.current = v; setState((s) => (s.fw === v ? s : { ...s, fw: v })) }
  }, [push, patch])

  const disconnect = useCallback(() => {
    const d = dev.current
    try { d.notify?.stopNotifications?.() } catch {  }
    try { d.device?.gatt?.disconnect?.() } catch {  }
    dev.current = { device: null, write: null, notify: null, floor: 0, txAt: null, txCmd: null, pageUntil: 0 }
    fwRef.current = null
    patch({ phase: 'idle', address: null, name: null, chrcCount: 0, mtuFloor: null, mtuEffective: null, fw: null })
  }, [patch])

  const connect = useCallback(async () => {
    if (!supported()) { err('此浏览器不支持 Web Bluetooth —— 见页面顶部支持说明。'); return }
    let picked = false
    try {
      toPhase('scanning')
      const device = await navigator.bluetooth.requestDevice({
        filters: [{ services: [SVC] }, { namePrefix: 'PRTS' }, { namePrefix: 'DE' }],
        optionalServices: [SVC],
      })
      picked = true
      device.addEventListener('gattserverdisconnected', () => {
        const d = dev.current
        if (d.device !== device || !d.write) return
        const held = d.linkedAt ? Math.round(Date.now() / 1000 - d.linkedAt) : null
        err(`设备断开了连接${held != null ? `（已连接 ${held}s）` : ''}。`)
        dev.current = { device: null, write: null, notify: null, floor: 0, txAt: null, txCmd: null, pageUntil: 0 }
        fwRef.current = null
        toPhase('idle', { address: null, name: null, chrcCount: 0, phaseLimit: null,
          mtuFloor: null, mtuEffective: null, fw: null })
      })
      toPhase('connecting', { address: device.id, name: device.name || null,
        phaseLimit: CONNECT_LIMIT_S + DISCOVER_LIMIT_S })
      const t0 = Date.now()
      const svc = await openService(device, SVC, (text) => log('warn', text))
      const chars = await svc.getCharacteristics()
      const write = await svc.getCharacteristic(WRITE)
      const notify = await svc.getCharacteristic(NOTIFY)
      await notify.startNotifications()
      notify.addEventListener('characteristicvaluechanged', onNotify)
      dev.current = { device, write, notify, floor: 0, txAt: null, txCmd: null, pageUntil: 0, linkedAt: Date.now() / 1000 }
      log('ok', `已连接 ${device.name || ''} · 建链 + GATT 发现 ${Math.round((Date.now() - t0) / 1000)}s · ${chars.length} 个特征值`)
      toPhase('linked', { chrcCount: chars.length, phaseLimit: null })
    } catch (e) {
      if (e?.name === 'NotFoundError' && !picked) toPhase('idle', { phaseLimit: null })
      else {
        const linuxHint = e?.name === 'NotFoundError' && /Linux/.test(navigator.userAgent) && !/Android/.test(navigator.userAgent)
          ? ' —— Linux 上取不到：设备把「查非主服务」也按主服务回，BlueZ 因此把它的服务都记成非主服务。请用带后端的版本。'
          : ''
        err(`连接失败：${e?.message || e}${linuxHint}`)
        toPhase('idle', { address: null, name: null, phaseLimit: null })
      }
    }
  }, [toPhase, err, log, onNotify])

  const sendCmd = useCallback(async (name, values) => {
    const d = dev.current
    if (!d.write) { err('未连接设备。', 'reject'); return }
    const spec = specFor(fwRef.current, name)
    if (!spec) { err(`未知命令 ${name}`, 'reject'); return }
    if (spec.blocked) { err(`${name} 被拦下：${spec.blocked}`, 'reject'); return }
    const { bytes, error } = buildFrame(spec, values)
    if (error) { err(error, 'reject'); return }
    const frame = Uint8Array.from(bytes)
    try {
      d.txAt = Date.now() / 1000
      d.txCmd = name
      if (spec.paged) d.pageUntil = d.txAt + 3.0
      push({ type: 'tx', at: d.txAt, cmd: name, hex: [...frame].map((x) => x.toString(16).padStart(2, '0')).join(''), size: frame.length })
      await d.write.writeValueWithResponse(frame)
    } catch (e) {
      err(`写 fef2 失败：${e?.message || e}`)
    }
  }, [push, err])

  const send = useCallback((msg) => {
    switch (msg.op) {
      case 'hello': return
      case 'scan': connect(); return
      case 'connect': connect(); return
      case 'disconnect': disconnect(); return
      case 'send': sendCmd(msg.cmd, msg.values); return
      case 'setFw': fwRef.current = msg.fw || null; patch({ fw: msg.fw || null }); return
      default: return
    }
  }, [connect, disconnect, sendCmd])

  return { state, entries, scan, online, send, setScan, clear: () => setEntries([]) }
}
