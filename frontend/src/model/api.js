import { EXPORT } from '../../config.js'
import { getLabelMaskSnapshot } from '../editor/masks.js'
import { decodeImage } from '../images/decode.js'
import { setOriginalImageSize } from '../images/metadata.js'
import { encodeMask } from './masks.js'
import { sessionFetch } from './session.js'

const API_URL = '/api'

const readError = async (response, fallback) => {
  try {
    const body = await response.json()
    return typeof body.detail === 'string' ? body.detail : fallback
  } catch {
    return fallback
  }
}

const encodeImage = async (file, targetWidth = null) => {
  const decoded = await decodeImage(file)

  try {
    setOriginalImageSize(file, decoded.width, decoded.height)
    const width = targetWidth == null
      ? decoded.width
      : Math.max(1, Math.round(targetWidth))
    const height = targetWidth == null
      ? decoded.height
      : Math.max(1, Math.round((decoded.height / decoded.width) * width))
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

const createExport = async (total, signal) => {
  const response = await sessionFetch('/export/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ total }),
    signal,
  })
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not start the export.'))
  }
  return response.json()
}

const runExport = async (id, files, width, signal) => {
  const body = new FormData()
  if (width != null) body.append('width', String(width))
  for (const file of files) {
    body.append('files', file, file.name)
  }

  const response = await sessionFetch(`/export/jobs/${id}`, {
    method: 'POST',
    body,
    signal,
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
      (batch.length >= EXPORT.batchFiles ||
        bytes + file.size > EXPORT.batchBytes)
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

const makeExportPlans = (files, width) =>
  makeExportBatches(files).map((batch) => ({ batch, width }))

const getExport = async (id, signal) => {
  const response = await sessionFetch(`/export/jobs/${id}`, { signal })
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not read export progress.'))
  }
  return response.json()
}

const pollWhilePending = async (work, poll) => {
  let pending = true
  let cancelWait = null
  const polling = (async () => {
    while (pending) {
      const elapsed = await new Promise((resolve) => {
        const timer = setTimeout(() => resolve(true), EXPORT.progressPollMs)
        cancelWait = () => {
          clearTimeout(timer)
          resolve(false)
        }
      })
      cancelWait = null
      if (!elapsed || !pending) return

      try {
        await poll()
      } catch {
        return
      }
    }
  })()

  try {
    return await work
  } finally {
    pending = false
    if (cancelWait) cancelWait()
    await polling
  }
}

const cancelExport = async (id) => {
  const response = await sessionFetch(`/export/jobs/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok && response.status !== 404) {
    throw new Error(await readError(response, 'Could not cancel the export.'))
  }
}

const getExportFile = async (id, signal) => {
  const response = await sessionFetch(`/export/jobs/${id}/file`, { signal })
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not download the export.'))
  }
  return response.blob()
}

export const exportAll = async (
  files,
  width,
  onProgress,
  signal,
) => {
  let id = null
  try {
    ({ id } = await createExport(files.length, signal))
    const plans = makeExportPlans(files, width)
    let lastProgress = 0
    const reportProgress = (done, total) => {
      if (
        !Number.isFinite(done) ||
        !Number.isFinite(total) ||
        total <= 0
      ) {
        return
      }
      const progress = Math.max(
        0,
        Math.min(100, Math.round((done / total) * 100)),
      )
      if (progress <= lastProgress) return
      lastProgress = progress
      onProgress(progress)
    }

    let done = 0
    const uploads = (async () => {
      for (const plan of plans) {
        await runExport(id, plan.batch, plan.width, signal)
        done += plan.batch.length
        reportProgress(done, files.length)
      }
    })()
    await pollWhilePending(uploads, async () => {
      const state = await getExport(id, signal)
      reportProgress(state.done, state.total)
    })

    const state = await getExport(id, signal)
    if (state.status !== 'ready') {
      throw new Error(state.error || 'Could not export the images.')
    }
    return getExportFile(id, signal)
  } catch (error) {
    if (error?.name === 'AbortError' && id) {
      await cancelExport(id).catch(() => {})
    }
    throw error
  }
}
