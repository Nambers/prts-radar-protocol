import { useEffect, useRef } from 'react'

export default function ScanSheet({ devices, scanning, onPick, onClose, onRescan }) {
  const ref = useRef(null)
  useEffect(() => { ref.current?.focus() }, [])

  return (
    <div className="sheet-backdrop" role="dialog" aria-modal="true" aria-label="扫描到的设备"
         onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet">
        <div className="pane-head">
          <h2>扫描结果</h2>
          <span className="en">le scan</span>
          <span className="spacer" />
          <button className="ghost" style={{ minHeight: 30 }} onClick={onRescan} disabled={scanning}>
            {scanning ? '扫描中…' : '重扫'}
          </button>
          <button ref={ref} className="ghost" style={{ minHeight: 30 }} onClick={onClose}>关闭</button>
        </div>
        <div className="pane-body flush" style={{ overflow: 'auto' }}>
          {!devices?.length && (
            <div className="empty">
              {scanning ? '扫描中…' : '没扫到设备。设备没在广播，或正被手机 App 占着（它只接受一条连接）。'}
            </div>
          )}
          {devices?.map((d, i) => {
            const firstOther = d.family === false && devices[i - 1]?.family === true
            return (
              <div key={d.address} style={{ display: 'contents' }}>
                {firstOther && (
                  <div className="group-head">
                    <span className="g">其余设备</span>
                    <span className="s">名字不以 PRTS / DE 开头</span>
                  </div>
                )}
                <button className="dev" data-family={d.family ? '1' : '0'}
                        onClick={() => onPick(d.address)}>
                  <span>
                    <span className="nm">{d.name || '(无名)'}</span>
                    {d.family && (
                      <span className="mark" style={{ marginLeft: 8 }} data-e="destructive">
                        目标机型
                      </span>
                    )}
                    {d.likely && (
                      <span className="mark" style={{ marginLeft: 6 }} data-e="write">带 fef0</span>
                    )}
                    <div className="ad">{d.address}</div>
                  </span>
                  <span className="rs">{d.rssi != null ? `${d.rssi} dBm` : ''}</span>
                  <span className="mark since">
                    {Object.keys(d.mfg || {}).length ? '有厂商数据' : ''}
                  </span>
                </button>
              </div>
            )
          })}
        </div>
        <div className="gate-foot">
          <span className="note">
            名字以 PRTS / DE 开头的排在前面并高亮 —— 那是目标机型的广播名前缀，
            比「带 fef0」更强的判据。从这里点进去会用扫描缓存直接建链，
            跳过「重新等一条广播」那一步（设备被别人占着时那步会干等到超时）。
          </span>
        </div>
      </div>
    </div>
  )
}
