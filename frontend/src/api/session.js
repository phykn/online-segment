import { API_URL } from './http.js'

let sessionId = ''
let generation = 0
let pending = null
const listeners = new Set()

const notify = () => {
  for (const listener of listeners) listener(sessionId)
}

const requestSession = async () => {
  const response = await fetch(`${API_URL}/sessions`, { method: 'POST' })
  if (!response.ok) throw new Error('Could not create a session.')

  const body = await response.json()
  if (typeof body.id !== 'string' || !body.id) {
    throw new Error('Could not create a session.')
  }
  return body.id
}

const startSession = () => {
  const requestedGeneration = generation
  const request = requestSession()
  const tracked = request
    .then((id) => {
      if (requestedGeneration !== generation) return ''
      sessionId = id
      notify()
      return id
    })
    .finally(() => {
      if (pending === tracked) pending = null
    })
  pending = tracked
  return tracked
}

export const getSession = async () => {
  while (!sessionId) {
    const id = await (pending ?? startSession())
    if (id) return id
  }
  return sessionId
}

export const resetSession = () => {
  generation += 1
  sessionId = ''
  notify()
}

const replaceExpiredSession = (expiredId) => {
  if (sessionId === expiredId) resetSession()
}

const abortError = () =>
  new DOMException('The operation was aborted.', 'AbortError')

const getSessionForRequest = (signal) => {
  if (!signal) return getSession()
  if (signal.aborted) return Promise.reject(abortError())

  const shared = getSession()
  return new Promise((resolve, reject) => {
    let settled = false
    const finish = (callback, value) => {
      if (settled) return
      settled = true
      signal.removeEventListener('abort', handleAbort)
      callback(value)
    }
    const handleAbort = () => finish(reject, abortError())

    signal.addEventListener('abort', handleAbort, { once: true })
    shared.then(
      (id) => finish(resolve, id),
      (error) => finish(reject, error),
    )
    if (signal.aborted) handleAbort()
  })
}

export const onSessionChange = (listener) => {
  listeners.add(listener)
  listener(sessionId)
  return () => listeners.delete(listener)
}

export const sessionFetch = async (path, options = {}, retry = true) => {
  const id = await getSessionForRequest(options.signal)
  const headers = new Headers(options.headers)
  headers.set('X-Session-ID', id)
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })

  if (response.status === 404 && retry) {
    const body = await response.clone().json().catch(() => null)
    if (body?.detail === 'session was not found.') {
      replaceExpiredSession(id)
      return sessionFetch(path, options, false)
    }
  }
  return response
}
