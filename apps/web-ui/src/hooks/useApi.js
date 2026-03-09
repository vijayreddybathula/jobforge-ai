import { useAuth } from '../contexts/AuthContext'
import { useRef } from 'react'

const BASE = '/api/v1'

/**
 * useApi — stable API client.
 *
 * IMPORTANT: returns a plain object whose function identities never change
 * between renders (backed by a ref). This means pages can safely list
 * `api.get`, `api.post`, etc. in useEffect dependency arrays without
 * triggering infinite re-render / request storms.
 */
export function useApi() {
  const { session, logout } = useAuth()

  // Keep latest session in a ref so the stable functions below can read it
  // without needing to be recreated every render.
  const sessionRef = useRef(session)
  sessionRef.current = session

  const logoutRef = useRef(logout)
  logoutRef.current = logout

  // Stable ref that holds all methods — created once, never recreated.
  const apiRef = useRef(null)

  if (!apiRef.current) {
    const getHeaders = () => {
      const h = { 'Content-Type': 'application/json' }
      if (sessionRef.current?.user_id) h['x-user-id'] = sessionRef.current.user_id
      return h
    }

    const handleResponse = async (res) => {
      if (res.status === 401) {
        logoutRef.current()
        throw new Error('Session expired. Please log in again.')
      }
      let data
      try { data = await res.json() } catch { data = {} }
      if (!res.ok) {
        const detail = data.detail
        const msg = typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map(d => d.msg || JSON.stringify(d)).join(', ')
            : `Request failed: ${res.status}`
        throw new Error(msg)
      }
      return data
    }

    const request = async (method, path, body = null) => {
      const res = await fetch(`${BASE}${path}`, {
        method,
        headers: getHeaders(),
        body: body != null ? JSON.stringify(body) : undefined,
      })
      return handleResponse(res)
    }

    const upload = async (path, file) => {
      // Do NOT set Content-Type — browser sets it automatically with the
      // correct multipart boundary when using FormData.
      const headers = {}
      if (sessionRef.current?.user_id) headers['x-user-id'] = sessionRef.current.user_id

      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch(`${BASE}${path}`, {
        method: 'POST',
        headers,   // NO Content-Type here
        body: formData,
      })
      return handleResponse(res)
    }

    apiRef.current = {
      get:    (path)       => request('GET',    path),
      post:   (path, body) => request('POST',   path, body),
      put:    (path, body) => request('PUT',    path, body),
      delete: (path)       => request('DELETE', path),
      upload,
    }
  }

  return apiRef.current
}
