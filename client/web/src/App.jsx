import { useEffect, useMemo, useState } from 'react'
import CommandRail from './components/CommandRail.jsx'
import FrameLedger from './components/FrameLedger.jsx'
import Inspector from './components/Inspector.jsx'
import LinkBand from './components/LinkBand.jsx'
import ReviewGate from './components/ReviewGate.jsx'
import ScanSheet from './components/ScanSheet.jsx'
import SupportNotice from './components/SupportNotice.jsx'
import { useTransport } from './lib/transport.js'
import { loadCatalog } from './lib/catalog.js'

const MTU_CUID = 123

export default function App() {
  const { state, entries, scan, online, send, setScan, clear } = useTransport()
  const [catalog, setCatalog] = useState(null)
  const [selected, setSelected] = useState(
    () => decodeURIComponent(location.hash.slice(1)) || 'GVER',
  )
  useEffect(() => {
    const onHash = () => setSelected(decodeURIComponent(location.hash.slice(1)) || 'GVER')
    addEventListener('hashchange', onHash)
    return () => removeEventListener('hashchange', onHash)
  }, [])
  const pick = (name) => { setSelected(name); location.hash = encodeURIComponent(name) }
  const [pickedId, setPickedId] = useState(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const fw = state.fw || null
  useEffect(() => {
    loadCatalog(fw).then(setCatalog).catch(() => {})
  }, [fw])

  useEffect(() => { if (scan) setSheetOpen(true) }, [scan])

  const cmd = useMemo(
    () => catalog?.commands.find((c) => c.name === selected) || null,
    [catalog, selected],
  )

  const lastTx = useMemo(() => {
    for (let i = entries.length - 1; i >= 0; i--) if (entries[i].type === 'tx') return entries[i]
    return null
  }, [entries])
  const lastRx = useMemo(() => {
    for (let i = entries.length - 1; i >= 0; i--) if (entries[i].type === 'rx') return entries[i]
    return null
  }, [entries])

  const lastTxSpec = catalog?.commands.find((c) => c.name === lastTx?.cmd)
  const awaiting = !!lastTx && !lastTxSpec?.no_reply &&
    (!lastRx || lastRx.at < lastTx.at) && Date.now() / 1000 - lastTx.at < 4
  const [, tick] = useState(0)
  useEffect(() => {
    if (!awaiting) return
    // 必须用 interval：无应答的命令没有 rx 事件推动重渲染，setTimeout 只会滴答一次
    const t = setInterval(() => tick((n) => n + 1), 400)
    return () => clearInterval(t)
  }, [awaiting])

  const selectedEntry = useMemo(
    () => entries.find((e) => e.id === pickedId) || lastRx || null,
    [entries, pickedId, lastRx],
  )

  const hazard = useMemo(() => {
    const lastErr = [...entries].reverse().find((e) => e.type === 'error')
    if (lastErr && Date.now() / 1000 - lastErr.at < 90) {
      return lastErr.kind === 'reject'
        ? { level: 'warn', title: '请求未放行', text: lastErr.text }
        : { level: 'error', title: '链路异常', text: lastErr.text }
    }
    const eff = state.mtuEffective
    if (state.phase === 'linked' && eff != null && eff < MTU_CUID) {
      const src = state.mtu != null && state.mtu >= eff ? 'BlueZ 报告' : '实测下界'
      return {
        level: 'warn',
        title: `ATT MTU ${eff} < ${MTU_CUID}（${src}）`,
        text: `设备按 ATT_MTU − 3 截断应答（不报错、不分片）：` +
          `CUID 分页会从 120 B 截到 ${eff - 3} B，BTOKEN 需要 ≥ 56。\n` +
          '读出来是空的不代表表里没数据 —— 先看本栏右侧「实测下界」' +
          '（= 收到过的最长帧 + 3，是观测不是报告值），' +
          '再用 btmon 看空口上的 ATT: Exchange MTU Request/Response 协商成了多少。',
      }
    }
    if (state.phase === 'linked' && eff == null) {
      return {
        level: 'warn',
        title: 'ATT MTU 未测出',
        text: '链路没报告 MTU（Web Bluetooth 不暴露；BlueZ < 5.62 也读不到），且还没收到过任何帧。\n' +
          '面板不会拿 bleak 的默认值 23 顶替。先发一条 GVER —— 收到应答后' +
          '「实测下界」就有值了（= 最长帧 + 3）。要地面实况用 btmon 看 ATT Exchange MTU。',
      }
    }
    const f = lastRx?.flags?.find((x) => x.level === 'error') ||
      lastRx?.flags?.find((x) => x.level === 'warn')
    if (f) return { level: f.level === 'error' ? 'error' : 'warn', title: `最近一帧：${lastRx.name}`, text: f.text }
    return null
  }, [entries, state.phase, state.mtu, state.mtuEffective, lastRx])

  return (
    <div className="shell">
      <SupportNotice />
      <LinkBand
        state={state} online={online} fw={fw}
        versions={catalog?.fw?.known}
        onScan={() => send({ op: 'scan', seconds: 6 })}
        onDisconnect={() => send({ op: 'disconnect' })}
        onSetFw={(v) => send({ op: 'setFw', fw: v })}
      />

      <div className="hazard-slot">
        {hazard ? (
          <div className="hazard" data-level={hazard.level} role="status">
            <span className="lb">{hazard.level === 'error' ? 'fault' : 'caution'}</span>
            <span className="tx"><b>{hazard.title}</b>{hazard.text}</span>
          </div>
        ) : (
          <div className="hazard" data-level="ok" role="status"
               style={{ borderColor: 'var(--rule)', background: 'var(--surface-2)', borderLeftColor: 'var(--rule-strong)' }}>
            <span className="lb" style={{ color: 'var(--ink-3)' }}>nominal</span>
            <span className="tx" style={{ color: 'var(--ink-2)' }}>
              真机链路 —— 无未处理异常。
            </span>
          </div>
        )}
      </div>

      <CommandRail catalog={catalog} selected={selected} onSelect={pick} fw={fw} />

      <div className="stage">
        <ReviewGate
          cmd={cmd}
          linked={state.phase === 'linked'}
          awaiting={awaiting}
          mtu={state.mtuEffective}
          onSend={(name, values) => send({ op: 'send', cmd: name, values })}
        />
        <FrameLedger entries={entries} selectedId={selectedEntry?.id}
                     onSelect={setPickedId} onClear={clear} />
      </div>

      <div className="dock">
        <Inspector entry={selectedEntry} state={state} fw={fw} />
      </div>

      {sheetOpen && (
        <ScanSheet
          devices={scan} scanning={state.phase === 'scanning'}
          onPick={(address) => { send({ op: 'connect', address }); setSheetOpen(false) }}
          onRescan={() => send({ op: 'scan', seconds: 6 })}
          onClose={() => { setSheetOpen(false); setScan(null) }}
        />
      )}
    </div>
  )
}
