/**
 * Authentication context.
 *
 * The token is held in localStorage (see lib/api.ts for why that tradeoff is
 * acceptable here) and the current user is re-validated against /auth/me on
 * load, so a stale or revoked token signs the user out rather than leaving the
 * UI in a falsely authenticated state.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, auth as tokenStore } from './api'

export interface User {
  id: number
  email: string
  display_name: string
}

interface AuthContextValue {
  user: User | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string, displayName?: string) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    if (!tokenStore.token) {
      setLoading(false)
      return
    }
    api
      .me()
      .then((result) => {
        if (!cancelled) setUser(result)
      })
      .catch(() => {
        // Expired or revoked: drop the token rather than appear signed in.
        tokenStore.clear()
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password)
    tokenStore.set(result.access_token)
    setUser(result.user)
  }, [])

  const signUp = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const result = await api.register(email, password, displayName)
      tokenStore.set(result.access_token)
      setUser(result.user)
    },
    [],
  )

  const signOut = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, signIn, signUp, signOut }),
    [user, loading, signIn, signUp, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside an AuthProvider')
  return context
}
