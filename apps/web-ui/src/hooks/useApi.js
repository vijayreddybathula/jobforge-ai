import { useAuth } from '../contexts/AuthContext'
import { useCallback } from 'react'

const BASE = '/api/v1'

export function useApi() {
  const { session, logout } = useAuth()

  const request = useCallback(async (method, path, body = null) => {
    const headers = { 'Content-Type': 'application/json' }
    if (session?.user_id) headers['x-user-id'] = session.user_id

    const res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })

    if (res.status === 401) {
      logout()
      throw new Error('Session expired. Please log in again.')
    }

    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || `Request failed: ${res.status}`)
    return data
  }, [session, logout])

  const upload = useCallback(async (path, file) => {
    const formData = new FormData()
    formData.append('file', file)
    const headers = {}
    if (session?.user_id) headers['x-user-id'] = session.user_id

    const res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (res.status === 401) { logout(); throw new Error('Session expired.') }
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Upload failed')
    return data
  }, [session, logout])

  return {
    get:    (path)        => request('GET',    path),
    post:   (path, body)  => request('POST',   path, body),
    put:    (path, body)  => request('PUT',    path, body),
    delete: (path)        => request('DELETE', path),
    upload,
  }
}
