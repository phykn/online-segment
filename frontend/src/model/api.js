import { getLabelMaskSnapshot } from '../editor/masks.js'
import { decodeImage } from '../images/decode.js'
import { setOriginalImageSize } from '../images/metadata.js'
import { encodeMask } from './masks.js'
import { sessionFetch } from './session.js'

const API_URL = '/api'
const EXPORT_BATCH_FILE_LIMIT = 8
const EXPORT_BATCH_BYTE_LIMIT = 32 * 1024 * 1024

const readError = async (response, fallback) => {
  try {
    const body = await response.json()
    return typeof body.detail === 'string' ? body.detail : fallback
  } catch {
    return fallback
  }
}

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
    body: JSON.stringify({
      image: await encodeImage(file, width),
    }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not predict the image.'))
  }
  return response.json()
}

const makeRefineItem = async (file, width) => {
  const mask = getLabelMaskSnapshot(file)
  return {
    image: await encodeImage(file, width),
    mask: mask ? encodeMask(mask) : null,
  }
}

export const refine = async (images, width) => {
  const items = await Promise.all(
    images.map((image) => makeRefineItem(image, width)),
  )
  const response = await sessionFetch('/refine', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ images: items }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not refine the model.'))
  }
}

export const exportMasks = async (files, width, height) => {
  const response = await fetch(`${API_URL}/export/archive`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ files, width, height }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Could not export the masks.'))
  }
  return response.blob()
}

const createExport = async (total) => {
  const response = await sessionFetch('/export/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ total }),
  })
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not start the export.'))
  }
  return response.json()
}

const runExport = async (id, files, width, forceLabels) => {
  const body = new FormData()
  body.append('width', String(width))
  for (const file of files) {
    const labels = forceLabels ? getLabelMaskSnapshot(file) : null
    body.append('files', file, file.name)
    body.append('labels', JSON.stringify(labels ? encodeMask(labels) : null))
  }

  const response = await sessionFetch(`/export/jobs/${id}`, {
    method: 'POST',
    body,
  })
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not export the images.'))
  }
}

const makeExportBatches = (files) => {
  const batches = []
  let batch = []
  let bytes = 0

  for (const file of files) {
    const exceedsLimit =
      batch.length > 0 &&
      (batch.length >= EXPORT_BATCH_FILE_LIMIT ||
        bytes + file.size > EXPORT_BATCH_BYTE_LIMIT)
    if (exceedsLimit) {
      batches.push(batch)
      batch = []
      bytes = 0
    }
    batch.push(file)
    bytes += file.size
  }
  if (batch.length) batches.push(batch)
  return batches
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

export const exportAll = async (files, width, forceLabels, onProgress) => {
  const { id } = await createExport(files.length)
  let done = 0
  for (const batch of makeExportBatches(files)) {
    await runExport(id, batch, width, forceLabels)
    done += batch.length
    onProgress(Math.round((done / files.length) * 100))
  }

  const state = await getExport(id)
  if (state.status !== 'ready') {
    throw new Error(state.error || 'Could not export the images.')
  }
  return getExportFile(id)
}
