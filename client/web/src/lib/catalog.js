import { TRANSPORT } from './transport.js'
import embedded from '../catalog.json'

const cache = new Map()

export function catalogFor(fw) {
  const { base, byFw } = embedded
  if (!fw) return base
  if (cache.has(fw)) return cache.get(fw)
  const d = byFw[fw]
  const out = d
    ? {
        ...base,
        fw: { ...base.fw, ...d.fw },
        commands: base.commands.map((c) => (d.commands[c.name] ? { ...c, ...d.commands[c.name] } : c)),
      }
    : { ...base, fw: { ...base.fw, version: fw, source: `未知版本 ${fw} —— 按 2.0.x 假定` } }
  cache.set(fw, out)
  return out
}

export async function loadCatalog(fw) {
  if (TRANSPORT === 'webble') return catalogFor(fw)
  const q = fw ? `?fw=${encodeURIComponent(fw)}` : ''
  const r = await fetch(`/api/catalog${q}`)
  return r.json()
}
