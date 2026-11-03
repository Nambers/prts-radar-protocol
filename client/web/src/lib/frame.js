export const SOF = 0x41
export const EOF = 0x51

export const hexs = (b) => [...b].map((x) => x.toString(16).padStart(2, '0')).join(' ')
export const hx2 = (n) => (n == null ? '--' : n.toString(16).padStart(2, '0'))

const bytesFromHex = (h) => {
  const s = String(h || '').replace(/[\s:]/g, '')
  const out = []
  for (let i = 0; i + 1 < s.length; i += 2) out.push(parseInt(s.slice(i, i + 2), 16))
  return out
}

export function nowUtc6() {
  const d = new Date()
  return [d.getUTCFullYear() % 100, d.getUTCMonth() + 1, d.getUTCDate(),
    d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds()]
}

export function encodeParams(spec, values) {
  const out = []
  for (const p of spec.params || []) {
    const v = values?.[p.name] ?? p.default
    if (p.kind === 'const') {
      out.push(...bytesFromHex(p.value))
    } else if (p.kind === 'u8') {
      const n = Number(v)
      if (!Number.isInteger(n) || n < 0 || n > 255) throw new Error(`${p.label} 需要 0–255 的整数`)
      out.push(n)
    } else if (p.kind === 'id6') {
      const h = String(v ?? '').replace(/[\s:]/g, '')
      if (!/^[0-9a-fA-F]{12}$/.test(h)) throw new Error(`${p.label} 需要 6 字节 = 12 个十六进制字符`)
      out.push(...bytesFromHex(h))
    } else if (p.kind === 'digits4') {
      const s = String(v ?? '')
      if (!/^\d{4}$/.test(s)) throw new Error(`${p.label} 需要 4 个数字字符（ASCII，不是 BCD）`)
      out.push(...[...s].map((c) => c.charCodeAt(0)))
    } else if (p.kind === 'time6') {
      const a = Array.isArray(v) && v.length === 6 ? v : nowUtc6()
      out.push(...a.map((x) => Number(x) & 0xff))
    } else if (p.kind === 'raw') {
      const h = String(v ?? '').replace(/\s/g, '')
      if (h && !/^([0-9a-fA-F]{2})+$/.test(h)) throw new Error(`${p.label} 需要偶数个十六进制字符`)
      out.push(...bytesFromHex(h))
    }
  }
  return out
}

export function buildFrame(spec, values) {
  if (!spec) return { bytes: [], roles: [], chkCalc: null, chkFw: null, usedFw: false, error: null }

  if (spec.raw) {
    const bytes = bytesFromHex(spec.raw)
    const roles = bytes.map((_, i) => (i === 0 ? 'sof' : i === bytes.length - 1 ? 'eof' : 'cmd'))
    return { bytes, roles, chkCalc: null, chkFw: null, usedFw: false, error: null }
  }

  let params
  try {
    params = encodeParams(spec, values)
  } catch (e) {
    return { bytes: [], roles: [], chkCalc: null, chkFw: null, usedFw: false, error: e.message }
  }

  const cmd = [...spec.name].map((c) => c.charCodeAt(0))
  const len = cmd.length + params.length + 4
  const body = [...cmd, len, ...params]
  const chkCalc = (SOF + body.reduce((a, b) => a + b, 0)) & 0xff
  const chkFw = params.length === 0 && spec.chk_fw != null ? spec.chk_fw : null
  const chk = chkFw ?? chkCalc

  const bytes = [SOF, ...body, chk, EOF]
  const roles = [
    'sof',
    ...cmd.map(() => 'cmd'),
    'len',
    ...params.map(() => 'param'),
    'chk',
    'eof',
  ]
  return { bytes, roles, chkCalc, chkFw, usedFw: chkFw != null && chkFw !== chkCalc, error: null }
}

export const ROLE_LABEL = {
  sof: '帧头 0x41 A',
  cmd: '命令名 ASCII',
  len: 'LEN = 整帧总长',
  param: '参数',
  chk: 'CHK',
  eof: '帧尾 0x51 Q',
}
