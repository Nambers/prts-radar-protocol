import { useLink } from './useLink.js'
import { useBleLink } from './useBleLink.js'

export const TRANSPORT = import.meta.env.VITE_TRANSPORT === 'webble' ? 'webble' : 'backend'

export const useTransport = TRANSPORT === 'webble' ? useBleLink : useLink
