import { getLabelMaskSnapshot } from '../editor/masks'
import { decodeImage } from '../images/decode'
import { setOriginalImageSize } from '../images/metadata'
import { sessionFetch } from './session'

const API_URL = '/api'

const readError = async (response, fallback) => {
  try {
    const body = await response.json()
    return typeof body.detail === 'string' ? body.detail : fallback
  } catch {
    return fallback
  }
}

const encodeRle = (data) => {
  const runs = []
  let value = data[0]
  let length = 1

  for (let index = 1; index < data.length; index += 1) {
    if (data[index] === value) {
      length += 1
    } else {
      runs.push([value, length])
      value = data[index]
      length = 1
    }
  }

  runs.push([value, length])
  return runs
}

export const encodeMask = (mask) => ({
  width: mask.width,
  height: mask.height,
  runs: encodeRle(mask.data),
})

const encodeImage = async (file, targetWidth = null) => {
  const mask = getLabelMaskSnapshot(file)
  const decoded = await decodeImage(file)

  try {
    setOriginalImageSize(file, decoded.width, decoded.height)
    const width = targetWidth
      ? Math.max(1, Math.round(targetWidth))
      : mask.width
    const height = targetWidth
      ? Math.max(1, Math.round((decoded.height / decoded.width) * width))
      : mask.height
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    context.imageSmoothingEnabled = true
    context.imageSmoothingQuality = 'high'
    context.drawImage(decoded.source, 0, 0, width, height)
    return canvas.toDataURL('image/png').split(',', 2)[1]
  } finally {
    decoded.dispose()
  }
}

const makeItem = async (file) => {
  const mask = getLabelMaskSnapshot(file)
  return {
    image: await encodeImage(file),
    mask: encodeMask(mask),
  }
}

export const apply = async (images) => {
  const items = await Promise.all(images.map(makeItem))
  const response = await sessionFetch('/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ images: items }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not train the model.'))
  }
}

export const predict = async (file, width) => {
  const response = await sessionFetch('/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: await encodeImage(file, width) }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not predict the image.'))
  }
  return response.json()
}

export const refine = async (images, target) => {
  const [items, targetItem] = await Promise.all([
    Promise.all(images.map(makeItem)),
    makeItem(target),
  ])
  const response = await sessionFetch('/refine', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ images: items, target: targetItem }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not refine the model.'))
  }
}

export const exportMask = async (mask, width, height) => {
  const response = await fetch(`${API_URL}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mask, width, height }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not export the mask.'))
  }
  return response.blob()
}

const createExport = async () => {
  const response = await sessionFetch('/export/jobs', { method: 'POST' })
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not start the export.'))
  }
  return response.json()
}

const runExport = async (id, files, width) => {
  const body = new FormData()
  body.append('width', String(width))
  for (const file of files) body.append('files', file, file.name)

  const response = await sessionFetch(`/export/jobs/${id}`, {
    method: 'POST',
    body,
  })
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not export the images.'))
  }
}

const getExport = async (id) => {
  const response = await sessionFetch(`/export/jobs/${id}`)
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not read export progress.'))
  }
  return response.json()
}

const getExportFile = async (id) => {
  const response = await sessionFetch(`/export/jobs/${id}/file`)
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not download the export.'))
  }
  return response.blob()
}

const wait = () => new Promise((resolve) => setTimeout(resolve, 200))

export const exportAll = async (files, width, onProgress) => {
  const { id } = await createExport()
  let taskError = null
  const task = runExport(id, files, width).catch((error) => {
    taskError = error
  })

  while (true) {
    await wait()
    if (taskError) throw taskError

    const state = await getExport(id)
    if (state.total > 0) {
      onProgress(Math.round((state.done / state.total) * 100))
    }
    if (state.status === 'error') {
      throw new Error(state.error || 'Could not export the images.')
    }
    if (state.status === 'ready') break
  }

  await task
  onProgress(100)
  return getExportFile(id)
}
