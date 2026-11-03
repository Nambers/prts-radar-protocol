import { TRANSPORT } from '../lib/transport.js'

const isDesktopLinux = () =>
  typeof navigator !== 'undefined' && /Linux/.test(navigator.userAgent) && !/Android/.test(navigator.userAgent)

export default function SupportNotice() {
  if (TRANSPORT !== 'webble') return null
  const supported = typeof navigator !== 'undefined' && !!navigator.bluetooth

  if (!supported) {
    return (
      <div className="hazard" data-level="error" role="status">
        <span className="lb">no web bluetooth</span>
        <span className="tx">
          <b>此浏览器不支持 Web Bluetooth</b>
          桌面 Chrome/Edge（Mac/Win）或 Android Chrome 可用；iPhone 用 Bluefy。Firefox / Safari 不支持。
          Linux 请用带后端的版本。
        </span>
      </div>
    )
  }
  if (isDesktopLinux()) {
    return (
      <div className="hazard" data-level="warn" role="status">
        <span className="lb">linux</span>
        <span className="tx">
          <b>Linux 上连不上这台设备</b>
          设备把「查非主服务」也按主服务回，BlueZ 因此把它的服务都记成非主服务，浏览器取不到
          <span className="mono">fef0</span>。请用带后端的版本。
        </span>
      </div>
    )
  }
  return null
}
