import { hx2 } from '../lib/frame.js'

function ToleranceRail({ checks }) {
  if (!checks?.length) return null
  return (
    <div className="tol">
      {checks.map((c) => {
        const vals = [c.observed, ...c.refs.map((r) => r.value)]
        let lo = Math.min(...vals)
        let hi = Math.max(...vals)
        if (hi - lo < 8) { const m = (hi + lo) / 2; lo = m - 4; hi = m + 4 }
        const pad = (hi - lo) * 0.16
        lo -= pad; hi += pad
        const pos = (v) => `${((v - lo) / (hi - lo)) * 100}%`
        return (
          <div className="tol-row" key={c.metric}>
            <div className="tol-top">
              <span className="m">{c.metric}</span>
              <span className="num" style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                观测 0x{hx2(c.observed)} = {c.observed}
              </span>
              <span className="verdict" data-w={c.within ? '1' : '0'}>
                {c.within ? '在容差内' : '落在容差外'}
              </span>
            </div>
            <div className="scale">
              {c.refs.map((r) => (
                <span key={r.label} className="tick ref"
                      data-hit={r.value === c.observed ? '1' : '0'}
                      style={{ left: pos(r.value) }}>
                  <span className="lb">{r.value}</span>
                </span>
              ))}
              <span className="tick obs" data-w={c.within ? '1' : '0'}
                    style={{ left: pos(c.observed) }} />
            </div>
            <div className="tol-refs">
              {c.refs.map((r) => (
                <span className="r" key={r.label}>
                  {r.label} <b>0x{hx2(r.value)}</b>
                  {r.value === c.observed ? ' ✓' : ` Δ${c.observed - r.value}`}
                </span>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function Inspector({ entry, state, fw }) {
  if (!entry) {
    return (
      <>
        <section className="pane">
          <div className="pane-head"><h2>来源胶囊</h2><span className="en">provenance</span></div>
          <div className="empty">在帧流水里点一条 —— 这里给出它的来源、校验与解出的字段。</div>
        </section>
        <section className="pane" style={{ gridRow: 'span 2' }}>
          <div className="pane-head"><h2>容差轨</h2><span className="en">tolerance</span></div>
          <div className="empty">
            选中一条应答后，这里把 LEN / CHK 的观测值放到允许范围里比对。
            <div style={{ marginTop: 10, color: 'var(--ink-4)', fontSize: 11, lineHeight: 1.7 }}>
              参考有两条：协议公式算出来的值，和固件常量表里手写死的值。
              两者本就不总一致 —— 两条都不中，才是真的异常。
            </div>
          </div>
        </section>
      </>
    )
  }

  const isRx = entry.type === 'rx'
  const outOfBand = (entry.checks || []).some((c) => !c.within)

  return (
    <>
      <section className="pane" aria-label="来源胶囊">
        <div className="pane-head">
          <h2>来源胶囊</h2>
          <span className="en">provenance</span>
        </div>
        <div className="pane-body flush">
          <div className="capsule">
            <div className="cap-head">
              <span className="nm">{isRx ? entry.name : entry.cmd}</span>
              <span className="mark" data-e={isRx ? 'read' : 'write'}>
                {isRx ? 'fef1 ◀ 设备' : 'fef2 ▶ 设备'}
              </span>
              <span className="sz">{entry.size} B</span>
            </div>
            <div className="cap-grid">
              <div>
                <div className="k">batch / 固件</div>
                <div className="v">{fw || '未读'}</div>
              </div>
              <div>
                <div className="k">phase / 链路</div>
                <div className="v">真机</div>
              </div>
              <div>
                <div className="k">integrity</div>
                <div className={`v${outOfBand ? ' out' : ''}`}>
                  {isRx ? (entry.checks?.length ? (outOfBand ? '容差外' : '容差内') : '无从校验') : '本地构造'}
                </div>
              </div>
              <div>
                <div className="k">rtt</div>
                <div className="v">{entry.rtt != null ? `${entry.rtt} ms` : '—'}</div>
              </div>
            </div>

            {isRx && entry.forCmd && (
              <dl className="kv">
                <dt>应答于</dt><dd className="mono">{entry.forCmd}</dd>
                {entry.template && (
                  <>
                    <dt>固件模板</dt>
                    <dd className="mono">
                      {entry.template.exact === false
                        ? '无该版档案（按 2.0.x 假定），不判定'
                        : entry.template.match ? '逐字节一致 ✓' : '不一致 ✗'}
                      <div style={{ color: 'var(--ink-3)' }}>
                        {entry.template.hex.replace(/(..)/g, '$1 ').trim()}
                      </div>
                    </dd>
                  </>
                )}
              </dl>
            )}

            {entry.fields?.length > 0 && (
              <dl className="kv" style={{ borderTop: '1px solid var(--rule)' }}>
                {entry.fields.map((f, i) => (
                  <span key={i} style={{ display: 'contents' }}>
                    <dt className={f.mono ? 'mono' : undefined}>{f.k}</dt>
                    <dd className={f.mono ? 'mono' : undefined}>{f.v}</dd>
                  </span>
                ))}
              </dl>
            )}

            <div className="raw">
              {(entry.hex || '').replace(/(..)/g, '$1 ').trim()}
              {entry.ascii && <div className="as">{entry.ascii}</div>}
            </div>
          </div>
        </div>
      </section>

      <section className="pane" aria-label="容差轨">
        <div className="pane-head">
          <h2>容差轨</h2>
          <span className="en">tolerance</span>
          <span className="spacer" />
          <span className="en">观测 vs 允许范围</span>
        </div>
        <div className="pane-body flush">
          {entry.checks?.length
            ? <ToleranceRail checks={entry.checks} />
            : <div className="empty">该帧没有可校验字段（固件本来就没写 LEN/CHK）。</div>}
          <div className="tol-rule" style={{ padding: '0 11px 11px' }}>
            {entry.checks?.length > 0 && '两条参考同时不中才算真异常 —— 固件常量表里手写死的值与公式值本就不一致。'}
          </div>
        </div>
      </section>

      <section className="pane">
        <div className="pane-head"><h2>标记</h2><span className="en">flags</span></div>
        <div className="pane-body">
          {entry.flags?.length
            ? entry.flags.map((f, i) => (
                <div key={i} className="hazard" data-level={f.level === 'error' ? 'error' : 'warn'}
                     style={{ marginBottom: 8 }}>
                  <span className="lb">{f.level}</span>
                  <span className="tx">{f.text}</span>
                </div>
              ))
            : <div className="empty">该帧无异常标记。</div>}
        </div>
      </section>
    </>
  )
}
