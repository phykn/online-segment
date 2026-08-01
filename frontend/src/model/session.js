const API_URL = '/api'

let sessionId = ''
let pending = null
const listeners = new Set()

const notify = () => {
  for (const listener of listeners) listener(sessionId)
}

const create = async () => {
  const response = await fetch(`${API_URL}/sessions`, { method: 'POST' })
  if (!response.ok) throw new Error('Could not create a session.')

  const body = await response.json()
  if (typeof body.id !== 'string' || !body.id) {
    throw new Error('Could not create a session.')
  }
  sessionId = body.id
  notify()
  return sessionId
}

export const getSession = () => {
  if (sessionId) return Promise.resolve(sessionId)
  if (!pending) {
    pending = create().finally(() => {
      pending = null
    })
  }
  return pending
}

export const resetSession = () => {
  sessionId = ''
  pending = null
  notify()
}

export const onSessionChange = (listener) => {
  listeners.add(listener)
  listener(sessionId)
  return () => listeners.delete(listener)
}

export const sessionFetch = async (path, options = {}, retry = true) => {
  const id = await getSession()
  const headers = new Headers(options.headers)
  headers.set('X-Session-ID', id)
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })

  if (response.status === 404 && retry) {
    const body = await response.clone().json().catch(() => null)
    if (body?.detail === 'session was not found.') {
      resetSession()
      return sessionFetch(path, options, false)
    }
  }
  return response
}
