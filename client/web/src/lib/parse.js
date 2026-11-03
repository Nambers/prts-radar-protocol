const RESP_EOF = 0x52

const hex = (b) => [...b].map((x) => x.toString(16).padStart(2, '0')).join('')
const printable = (b) => [...b].map((x) => (x >= 0x20 && x < 0x7f ? String.fromCharCode(x) : '·')).join('')

function asciiName(data) {
  let i = 0
  while (i < data.length && ((data[i] >= 0x41 && data[i] <= 0x5a) || (data[i] >= 0x61 && data[i] <= 0x7a))) i += 1
  return i >= 2 ? String.fromCharCode(...data.slice(0, i)) : null
}

function check(r, metric, observed, refs) {
  const within = refs.some((x) => x.value === observed)
  r.checks.push({ metric, observed, within, refs })
}

function decodeParams(name, params, r) {
  if (!params.length) return
  if (name === 'BVER') {
    const v = printable(params).replace(/·+$/, '').trim()
    r.fields.push({ k: '固件版本', v, mono: true })
  } else if (name === 'BVBAT') {
    const lvl = { 0: '充电中', 1: '满' }[params[0]] ?? `等级 ${params[0]}（6=极低）`
    r.fields.push({ k: '电量', v: `0x${params[0].toString(16).padStart(2, '0')} → ${lvl}` })
    if (params.length >= 2) r.fields.push({ k: '提醒音（TORLE）', v: params[1] })
  } else if (name === 'BGBRGT') {
    const lvl = { 0x1e: 0, 0x3c: 1, 0x5a: 2 }[params[0]]
    r.fields.push({ k: '亮度参数', v: `0x${params[0].toString(16).padStart(2, '0')}${lvl != null ? ` → 等级 ${lvl}` : ''}` })
  } else {
    r.fields.push({ k: '参数', v: hex(params).replace(/(..)/g, '$1 ').trim(), mono: true })
  }
}

export function parseReply(data, { spec = null, tplHex = null, mtu = null, paging = false } = {}) {
  const r = {
    hex: hex(data), ascii: printable(data), size: data.length,
    name: null, len_field: null, len_actual: data.length, chk_field: null,
    checks: [], fields: [], flags: [], template: null,
  }
  if (!data.length) return r

  if (data.length === 2 && data[0] === RESP_EOF && data[1] === RESP_EOF) {
    r.name = '(CUID 结束标记)'
    r.fields.push({ k: '52 52', v: '分页推送结束 —— 20 页已推完' })
    return r
  }
  if (data.length === 120 || (paging && data.length % 12 === 0 && data.length >= 12)) {
    r.name = '(CUID 分页)'
    for (let i = 0; i + 12 <= data.length; i += 12) {
      const rec = data.slice(i, i + 12)
      r.fields.push({ k: `记录 ${i / 12}`, v: hex(rec.slice(0, 6)) + ' … ' + hex(rec.slice(6)), mono: true })
    }
    if (data.length !== 120) {
      r.flags.push({ level: 'warn', text: `分块只有 ${data.length} B（正常 120）—— MTU ${mtu || '?'} 不足，帧被截断，不是表里没数据。` })
    }
    return r
  }

  if (spec?.name === 'TIME?' || (data.length === 8 && data[0] === 0x42 && data[data.length - 1] === RESP_EOF && !asciiName(data))) {
    r.name = '(读时间应答·无命令名)'
    if (data.length >= 7) {
      const [yy, mo, dd, hh, mm, ss] = data.slice(1, 7)
      const p = (n) => String(n).padStart(2, '0')
      r.fields.push({ k: '设备 RTC', v: `20${p(yy)}-${p(mo)}-${p(dd)} ${p(hh)}:${p(mm)}:${p(ss)} UTC`, mono: true })
    }
    r.flags.push({ level: 'info', text: '该应答既无命令名也无 LEN/CHK（固件如此），无从校验。' })
    return r
  }

  if (data[data.length - 1] !== RESP_EOF) {
    r.flags.push({ level: 'warn', text: `帧尾不是 0x52 'R'，实际 0x${data[data.length - 1].toString(16).padStart(2, '0')}` })
  }

  const name = asciiName(data)
  r.name = name || '(未识别)'

  if (name === 'BSPARM' || name === 'BRADAR') {
    r.chk_field = data[data.length - 2]
    r.flags.push({ level: 'info', text: '该应答没有 LEN 字段（固件如此）。' })
    const sum = data.slice(0, -2).reduce((a, b) => a + b, 0) & 0xff
    check(r, 'CHK', data[data.length - 2], [{ label: '公式 sum&0xFF', value: sum }])
  } else if (name && data.length >= name.length + 3) {
    r.len_field = data[name.length]
    r.chk_field = data[data.length - 2]
    const params = data.slice(name.length + 1, -2)
    decodeParams(name, params, r)
    check(r, 'LEN', r.len_field, [{ label: '整帧总长', value: r.len_actual }])
    const sum = data.slice(0, -2).reduce((a, b) => a + b, 0) & 0xff
    const refs = [{ label: '公式 sum&0xFF', value: sum }]
    const fw = spec?.reply?.tpl
    if (fw && fw.length >= 4) {
      const tb = fromHex(fw)
      if (tb.length >= 2) refs.push({ label: '固件模板值', value: tb[tb.length - 2] })
    }
    check(r, 'CHK', r.chk_field, refs)
  }

  if (tplHex) {
    const t = fromHex(tplHex)
    let match = t.length === data.length
    if (match) for (let i = 0; i < t.length; i++) if (t[i] !== data[i]) { match = false; break }
    r.template = { exact: true, match, hex: tplHex }
    if (!match) r.flags.push({ level: 'warn', text: '与固件模板逐字节不一致 —— 可能是版本没锁对，或这条命令本就运行时拼帧。' })
  }
  return r
}

function fromHex(h) {
  const s = String(h || '').replace(/[\s:]/g, '')
  const out = new Uint8Array(Math.floor(s.length / 2))
  for (let i = 0; i + 1 < s.length; i += 2) out[i / 2] = parseInt(s.slice(i, i + 2), 16)
  return out
}

export function versionFromReply(data) {
  if (data.length >= 11 && String.fromCharCode(...data.slice(0, 4)) === 'BVER') {
    return printable(data.slice(5, 10)).replace(/·+$/, '').trim() || null
  }
  return null
}
