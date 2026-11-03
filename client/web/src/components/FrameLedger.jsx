import { useEffect, useRef } from 'react'

const clock = (t) => {
  const d = new Date((t || 0) * 1000)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:` +
    `${String(d.getSeconds()).padStart(2, '0')}.${String(d.getMilliseconds()).padStart(3, '0')}`
}

const short = (h, n = 46) => {
  const s = (h || '').replace(/(..)/g, '$1 ').trim()
  return s.length > n ? `${s.slice(0, n)}…` : s
}

export default function FrameLedger({ entries, selectedId, onSelect, onClear }) {
  const boxRef = useRef(null)
  const stick = useRef(true)

  useEffect(() => {
    const el = boxRef.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [entries.length])

  const rxCount = entries.filter((e) => e.type === 'rx').length

  return (
    <section className="pane">
      <div className="pane-head">
        <h2>帧流水</h2>
        <span className="en">fef2 ▶ / ◀ fef1</span>
        <span className="spacer" />
        <span className="en">{rxCount} rx · {entries.length} 条</span>
        <button className="ghost" style={{ minHeight: 26, fontSize: 11 }} onClick={onClear}>清空</button>
      </div>
      <div
        ref={boxRef}
        className="pane-body flush"
        onScroll={(e) => {
          const el = e.currentTarget
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
        }}
      >
        {entries.length === 0 && (
          <div className="empty">还没有帧。连上设备后从复核门下发一条命令。</div>
        )}
        <div className="ledger">
          {entries.map((e) => {
            if (e.type === 'tx') {
              return (
                <button key={e.id} className="entry" data-dir="tx"
                        aria-selected={selectedId === e.id} onClick={() => onSelect(e.id)}>
                  <span className="t">{clock(e.at)}</span>
                  <span className="dir">▶</span>
                  <span className="main">
                    <span className="nm">{e.cmd}</span>
                    <span className="hx">{short(e.hex)}</span>
                  </span>
                  <span className="tail"><span className="chip">{e.size} B</span></span>
                </button>
              )
            }
            if (e.type === 'rx') {
              const out = (e.checks || []).some((c) => !c.within)
              const tpl = e.template
              return (
                <button key={e.id} className="entry" data-dir="rx"
                        aria-selected={selectedId === e.id} onClick={() => onSelect(e.id)}>
                  <span className="t">{clock(e.at)}</span>
                  <span className="dir">◀</span>
                  <span className="main">
                    <span className="nm">{e.name}</span>
                    <span className="hx">{short(e.hex)}</span>
                  </span>
                  <span className="tail">
                    {tpl && (
                      tpl.exact === false
                        ? <span className="chip" title="该固件版本无 profiles/ 档案，模板按 2.0.x 假定 —— 不作「一致/不一致」判定">模板 ?</span>
                        : <span className="chip" data-s={tpl.match ? 'tpl' : 'out'}>
                            模板{tpl.match ? '一致' : '不一致'}
                          </span>
                    )}
                    {(e.checks || []).length > 0 && (
                      <span className="chip" data-s={out ? 'out' : 'in'}>
                        {out ? '容差外' : '容差内'}
                      </span>
                    )}
                    {e.rtt != null && <span className="chip">{e.rtt} ms</span>}
                    <span className="chip">{e.size} B</span>
                  </span>
                </button>
              )
            }
            const level = e.type === 'error' ? 'error' : e.level || 'info'
            return (
              <div key={e.id} className="entry" data-dir={e.type === 'error' ? 'err' : 'log'}
                   data-level={level} style={{ cursor: 'default' }}>
                <span className="t">{clock(e.at)}</span>
                <span className="dir">{e.type === 'error' ? '✕' : '·'}</span>
                <span className="main"><span className="txt">{e.text}</span></span>
                <span className="tail" />
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
