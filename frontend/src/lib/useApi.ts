import { useEffect, useState } from 'react'
import { api } from './api'

export interface ApiState<T> {
  data: T | null
  error: string | null
  loading: boolean
}

export function useApi<T>(path: string | null): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: !!path })

  useEffect(() => {
    if (!path) return
    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: null }))
    api
      .get<T>(path)
      .then((data) => !cancelled && setState({ data, error: null, loading: false }))
      .catch((e: Error) => !cancelled && setState({ data: null, error: e.message, loading: false }))
    return () => {
      cancelled = true
    }
  }, [path])

  return state
}
