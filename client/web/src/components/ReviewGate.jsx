import { useEffect, useMemo, useState } from 'react'
import { ROLE_LABEL, buildFrame, hx2, nowUtc6 } from '../lib/frame.js'

const EFFECT_TEXT = {
  read: '只读 —— 不改变设备任何状态',
  write: '写入 —— 改变设备状态，有回滚手段',
  destructive: '不可逆 —— 清表 / 解绑 / 覆盖身份',
}

function ParamField({ p, value, onChange }) {
  if (p.kind === 'const') {
    return (
      <div className="field">
        <label>{p.label}</label>
        <input className="mono" value={p.value} readOnly tabIndex={-1} />
        <span className="hint">{p.help}</span>
      </div>
    )
  }
  if (p.kind === 'u8' && p.options) {
    return (
      <div className="field">
        <label htmlFor={`p-${p.name}`}>{p.label}</label>
        <select id={`p-${p.name}`} value={value ?? p.default}
                onChange={(e) => onChange(Number(e.target.value))}>
          {p.options.map((o) => <option key={o.v} value={o.v}>{o.t}</option>)}
        </select>
        <span className="hint">{p.help}</span>
      </div>
    )
  }
  if (p.kind === 'time6') {
    const v = Array.isArray(value) ? value : nowUtc6()
    return (
      <div className="field" style={{ minWidth: 230 }}>
        <label htmlFor={`p-${p.name}`}>{p.label}</label>
        <div style={{ display: 'flex', gap: 6 }}>
          <input id={`p-${p.name}`} className="mono" style={{ flex: 1 }}
                 value={v.map((x) => String(x).padStart(2, '0')).join(' ')}
                 onChange={(e) => onChange(e.target.value.trim().split(/\s+/).map(Number))} />
          <button type="button" className="ghost" onClick={() => onChange(nowUtc6())}>取当前 UTC</button>
        </div>
        <span className="hint">{p.help}</span>
      </div>
    )
  }
  const invalid =
    (p.kind === 'id6' && value && !/^[0-9a-fA-F\s:]{12,17}$/.test(String(value))) ||
    (p.kind === 'digits4' && value && !/^\d{4}$/.test(String(value)))
  return (
    <div className="field" style={{ minWidth: p.kind === 'id6' ? 210 : 150 }}>
      <label htmlFor={`p-${p.name}`}>{p.label}</label>
      <input id={`p-${p.name}`} className="mono" aria-invalid={invalid || undefined}
             placeholder={p.kind === 'id6' ? 'aabbccddeeff' : ''}
             value={value ?? p.default ?? ''} onChange={(e) => onChange(e.target.value)} />
      <span className="hint">{p.help}</span>
    </div>
  )
}

export default function ReviewGate({ cmd, linked, awaiting, mtu, onSend }) {
  const [values, setValues] = useState({})
  const [ack, setAck] = useState(false)
  const [locked, setLocked] = useState(false)

  useEffect(() => { setValues({}); setAck(false) }, [cmd?.name])

  const built = useMemo(() => buildFrame(cmd, values), [cmd, values])

  if (!cmd) {
    return (
      <section className="gate">
        <div className="empty">从左侧命令目录选一条 —— 复核门会先把完整字节和影响摊开，再让你下发。</div>
      </section>
    )
  }

  const destructive = cmd.effect === 'destructive'
  const mtuShort = cmd.mtu_min && mtu != null && mtu < cmd.mtu_min
  const ready = linked && !built.error && !awaiting && (!destructive || ack) && !cmd.blocked

  const submit = () => {
    onSend(cmd.name, values)
    setLocked(true)
    setTimeout(() => setLocked(false), 460)
    if (destructive) setAck(false)
  }

  return (
    <section className="gate" data-effect={cmd.effect} aria-label={`复核门 ${cmd.name}`}>
      <div className="gate-head">
        <h2>{cmd.name}</h2>
        <span className="sub">{cmd.title}</span>
        <span style={{ marginLeft: 'auto' }} className="mark" data-e={cmd.effect}>
          {EFFECT_TEXT[cmd.effect]}
        </span>
      </div>

      <div className="gate-body">
        {cmd.params?.length > 0 && (
          <div className="field-row">
            {cmd.params.map((p) => (
              <ParamField key={p.name} p={p} value={values[p.name]}
                          onChange={(v) => setValues((s) => ({ ...s, [p.name]: v }))} />
            ))}
          </div>
        )}

        <div>
          <div className="bytes" role="img"
               aria-label={`将要写入 fef2 的 ${built.bytes.length} 字节`}>
            {built.error
              ? <span style={{ color: 'var(--critical-ink)', fontSize: 12 }}>{built.error}</span>
              : built.bytes.map((b, i) => (
                  <span key={i} className="byte" data-role={built.roles[i]}
                        data-fw={built.roles[i] === 'chk' && built.usedFw ? '1' : '0'}
                        title={ROLE_LABEL[built.roles[i]]}>
                    {hx2(b)}
                  </span>
                ))}
          </div>
          <div className="byte-legend" style={{ marginTop: 6 }}>
            <span><b>写入</b> fef2 · {built.bytes.length} B</span>
            <span><b>帧头/尾</b> A…Q</span>
            <span><b>LEN</b> 整帧总长</span>
            <span><b>参数</b> 绿底</span>
            {built.chkCalc != null && (
              <span>
                <b>CHK</b> 公式 {hx2(built.chkCalc)}
                {built.chkFw != null && <> · 固件立即数 {hx2(built.chkFw)}</>}
                {built.usedFw && (
                  <span style={{ color: 'var(--amber-ink)', fontWeight: 600 }}>
                    {' '}→ 取固件值（差 {built.chkFw - built.chkCalc}）
                  </span>
                )}
              </span>
            )}
          </div>
        </div>

        <dl className="consequence">
          <dt>应答</dt>
          <dd>
            {cmd.no_reply
              ? <span className="warn">{cmd.no_reply}</span>
              : cmd.reply
                ? <>{cmd.reply.name} · {cmd.reply.len} B{cmd.reply.note ? ` —— ${cmd.reply.note}` : ''}</>
                : <span className="warn">无应答（空实现）</span>}
          </dd>

          {}
          {cmd.verified && (
            <>
              <dt>分发器校验</dt>
              <dd style={{ whiteSpace: 'pre-line' }}>{cmd.verified}</dd>
            </>
          )}

          {cmd.persists && (<><dt>落盘</dt><dd className="warn">{cmd.persists}</dd></>)}

          <dt>回滚</dt>
          <dd className={cmd.rollback ? '' : destructive ? 'crit' : ''}>
            {cmd.rollback || (destructive ? '无 —— 下发后没有恢复手段' : '不适用（不改变状态）')}
          </dd>

          {cmd.mtu_min && (
            <>
              <dt>MTU 门限</dt>
              <dd className={mtuShort ? 'crit' : ''}>
                需要 ≥ {cmd.mtu_min}，当前 {mtu ?? '未测出'}
                {mtuShort && ' —— 应答会被截断'}
                {mtu == null && ' —— 没测出来就不下结论；先发 GVER 看实测下界'}
              </dd>
            </>
          )}

          {cmd.note && (<><dt>注</dt><dd style={{ whiteSpace: 'pre-line' }}>{cmd.note}</dd></>)}

          {}
          {cmd.note_fw && (
            <>
              <dt>本版</dt>
              <dd style={{ whiteSpace: 'pre-line' }}>{cmd.note_fw}</dd>
            </>
          )}
          {cmd.notes_other?.length > 0 && (
            <>
              <dt>其他世代</dt>
              <dd>
                {cmd.notes_other.map((n, i) => (
                  <details key={i} style={{ marginBottom: 2 }}>
                    <summary style={{ cursor: 'pointer', color: 'var(--ink-3)' }}>
                      {n.range}
                    </summary>
                    <div style={{ whiteSpace: 'pre-line', color: 'var(--ink-2)', paddingTop: 2 }}>
                      {n.text}
                    </div>
                  </details>
                ))}
              </dd>
            </>
          )}
          {cmd.blocked && (<><dt>已拦下</dt><dd className="crit">{cmd.blocked}</dd></>)}
        </dl>
      </div>

      <div className="gate-foot">
        {destructive && !cmd.blocked && (
          <button type="button" className="ghost" aria-pressed={ack}
                  onClick={() => setAck((a) => !a)}>
            {ack ? '✓ 已确认回滚条件' : '确认已读回滚条件'}
          </button>
        )}
        <span className="note">
          {!linked ? '未连接 —— 先扫描并连上设备'
            : cmd.blocked ? '本条不放行'
            : destructive && !ack ? '不可逆操作：先确认回滚条件'
            : awaiting ? '正在等应答…'
            : '按下即写入 fef2'}
        </span>
        <button className="plate" data-effect={cmd.effect}
                data-busy={awaiting ? '1' : '0'} data-locked={locked ? '1' : '0'}
                disabled={!ready} onClick={submit}>
          下发 {cmd.name}
        </button>
      </div>
    </section>
  )
}
