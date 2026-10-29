import { PROGRESS_POLL_MS } from '../../config.js'
import { readError } from './http.js'
import { sessionFetch } from './session.js'

export const predictImage = async (image, options = {}, onProgress = () => {}) => {
  const polling = new AbortController()
  let reading = false
  const timer = setInterval(async () => {
    if (reading) return
    reading = true
    try {
      const response = await sessionFetch('/predict/status', { signal: polling.signal })
      if (response.ok) {
        const state = await response.json()
        if (!polling.signal.aborted) onProgress(state)
      }
    } catch { /* The prediction request reports actionable errors. */ }
    finally { reading = false }
  }, PROGRESS_POLL_MS)
  try {
    const response = await sessionFetch('/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image, ...options }),
    })

    if (!response.ok) {
      throw new Error(await readError(response, 'Could not predict the image.'))
    }
    return response.json()
  } finally {
    clearInterval(timer)
    polling.abort()
  }
}
