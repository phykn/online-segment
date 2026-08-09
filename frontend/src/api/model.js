import { readError } from './http.js'
import { sessionFetch } from './session.js'

export const applyModel = async (items) => {
  const response = await sessionFetch('/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ images: items }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not train the model.'))
  }
}

export const predictImage = async (image) => {
  const response = await sessionFetch('/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not predict the image.'))
  }
  return response.json()
}
