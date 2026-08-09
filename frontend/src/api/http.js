export const API_URL = '/api'

export const readError = async (response, fallback) => {
  try {
    const body = await response.json()
    return typeof body.detail === 'string' ? body.detail : fallback
  } catch {
    return fallback
  }
}
