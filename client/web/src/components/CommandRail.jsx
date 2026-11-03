import { useEffect, useRef } from 'react'

const EFFECT_TEXT = { read: '只读', write: '可回滚', destructive: '不可逆' }

export default function CommandRail({ catalog, selected, onSelect, fw }) {
  const boxRef = useRef(null)
  const selRef = useRef(null)

  useEffect(() => {
    const box = boxRef.current
    const btn = selRef.current
    if (!box || !btn) return
    const b = btn.getBoundingClientRect()
    const c = box.getBoundingClientRect()
    if (b.top < c.top || b.bottom > c.bottom) {
      box.scrollTop += b.top - c.top - (c.height - b.height) / 2
    }
  }, [selected, catalog])

  if (!catalog) return <aside className="pane rail"><div className="empty">目录加载中…</div></aside>

  return (
    <aside className="pane rail">
      <div className="pane-head" style={{ flexWrap: 'wrap', rowGap: 2 }}>
        <h2>命令目录</h2>
        <span className="en">dispatcher · {catalog.commands.length}</span>
        {}
        <span style={{ width: '100%', fontSize: 10, lineHeight: 1.4,
                       color: catalog.fw?.exact ? 'var(--signal-ink)' : 'var(--amber-ink)' }}>
          {catalog.fw?.exact ? `按固件 ${catalog.fw.version} 解释` : '版本未知'}
          {' · '}{catalog.fw?.source}
        </span>
      </div>
      <div ref={boxRef} className="pane-body flush" role="listbox" aria-label="命令目录">
        {catalog.groups.map((g) => {
          const items = catalog.commands.filter((c) => c.group === g.key)
          if (!items.length) return null
          return (
            <div key={g.key}>
              <div className="group-head">
                <span className="g">{g.label}</span>
                <span className="s">{g.sub}</span>
              </div>
              {items.map((c) => {
                const unavailable = c.absent
                return (
                  <button
                    key={c.name}
                    ref={selected === c.name ? selRef : null}
                    role="option"
                    aria-selected={selected === c.name}
                    data-effect={c.effect}
                    className="tab"
                    disabled={!!c.blocked || c.absent}
                    onClick={() => onSelect(c.name)}
                    title={c.blocked || c.note || c.title}
                  >
                    <span className="row1">
                      <span className="nm">{c.name}</span>
                      <span className="ti">{c.title}</span>
                    </span>
                    <span className="row2">
                      <span className="mark" data-e={c.effect}>{EFFECT_TEXT[c.effect]}</span>
                      <span className="mark since"
                            title={c.since_evidence === 'soft'
                              ? '起始版本是推断的，未在旧版真机上核对 —— 不拦截'
                              : '两路证据互证'}>
                        {unavailable ? `本版无（需 ≥ ${c.since}）` : `首见 ${c.since}`}
                        {c.since_evidence === 'soft' ? ' ?' : ''}
                      </span>
                      {c.suspect_absent && !unavailable && (
                        <span className="mark" data-e="write">本版存疑</span>
                      )}
                      {c.blocked && <span className="mark" data-e="destructive">已拦下</span>}
                    </span>
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>
    </aside>
  )
}
