import { useEffect, useState } from 'react'
import { TRANSPORT } from '../lib/transport.js'

const PHASE_TEXT = {
  idle: '空闲',
  scanning: '扫描中',
  connecting: '建链 + GATT 发现',
  discovering: '枚举特征值',
  linked: '已连接',
  disconnecting: '断开中',
}

const BUSY = ['scanning', 'connecting', 'discovering', 'disconnecting']

function useElapsed(active, since) {
  const [, tick] = useState(0)
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => tick((n) => n + 1), 500)
    return () => clearInterval(t)
  }, [active])
  if (!active || !since) return null
  return Math.max(0, Math.round(Date.now() / 1000 - since))
}

function Cell({ k, children, grow, dim }) {
  return (
    <div className={`cell${grow ? ' grow' : ''}`}>
      <span className="k">{k}</span>
      <span className={`v${dim ? ' dim' : ''}`}>{children}</span>
    </div>
  )
}

export default function LinkBand({ state, online, fw, versions, onScan, onDisconnect, onSetFw }) {
  const busy = BUSY.includes(state.phase)
  const linked = state.phase === 'linked'
  const connecting = state.phase === 'connecting' || state.phase === 'discovering'
  const archived = [...(versions || [])].reverse()
  const fwSel = fw && archived.includes(fw) ? fw : ''
  const elapsed = useElapsed(busy, state.phaseSince)
  const limit = connecting ? state.phaseLimit : null

  return (
    <header className="band pane">
      <div className="spine" aria-hidden="true" />
      <div className="cells">
        <Cell k="link / 链路">
          <span className="phase" data-p={state.phase}>
            <span className="dot" aria-hidden="true" />
            {PHASE_TEXT[state.phase] || state.phase}
            {elapsed != null && (
              <span style={{ color: elapsed > 15 && connecting ? 'var(--amber-ink)' : 'var(--ink-3)' }}>
                {' '}{elapsed}s{limit ? ` / 上限 ${Math.round(limit)}s` : ''}
              </span>
            )}
          </span>
        </Cell>
        <Cell k="transport / 传输">
          {TRANSPORT === 'webble' ? '真机 · Web Bluetooth' : '真机 · BlueZ'}
        </Cell>
        <Cell k="adapter / 适配器" dim={!state.adapter}>
          {state.adapter || '自动（$PRTS_HCI › hci1 › 首个）'}
        </Cell>
        <Cell k="target / 目标" grow dim={!state.address}>
          {state.address || '未选择'}
        </Cell>
        <Cell k="fw / 固件">
          <select
            className="fw-pick"
            value={fwSel}
            onChange={(e) => onSetFw(e.target.value)}
            title="解释用的固件版本 —— 目录、应答模板、帧注释都按它走。只列有档案的版本；没档案的落到「2.0.x 默认」。发 GVER 后：有档案就自动切过去，没档案停在默认。仍可随时手改。"
          >
            <option value="">2.0.x · 默认（无精确档案）</option>
            {archived.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </Cell>
        {}
        <Cell k="att mtu / 报告" dim={state.mtu == null}>
          {state.mtu == null ? '未测' : state.mtu}
        </Cell>
        <Cell k="实测下界" dim={!state.mtuFloor}>
          {state.mtuFloor ? `≥ ${state.mtuFloor}` : '—'}
        </Cell>
        <Cell k="chrc / 特征值" dim={!state.chrcCount}>{state.chrcCount || '—'}</Cell>

        <div className="cell act">
          <button className="ghost" onClick={onScan} disabled={busy || linked || !online}>
            扫描设备
          </button>
          <button className="plate" onClick={onDisconnect}
                  data-effect={connecting ? 'destructive' : undefined}
                  disabled={!linked && !busy}>
            {connecting ? '取消连接' : '断开链路'}
          </button>
        </div>
      </div>
      {connecting && elapsed > 15 && (
        <div className="cell" style={{ borderRight: 0, borderTop: '1px solid var(--rule)', width: '100%' }}>
          <span className="k">进度</span>
          <span className="v dim" style={{ whiteSpace: 'normal', fontSize: 11.5 }}>
            该设备连接间隔 1000 ms，一个连接事件只走一个 ATT PDU —— 完整 GATT 发现常要 30–60 s，属正常。
          </span>
        </div>
      )}
      {busy && <div className="rule-travel" aria-hidden="true" />}
      {!online && (
        <div className="rule-travel" aria-hidden="true"
             style={{ background: 'var(--critical)' }} />
      )}
    </header>
  )
}
