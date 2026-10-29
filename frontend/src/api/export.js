import { EXPORT } from '../../config.js'
import { API_URL, readError } from './http.js'
import { sessionFetch } from './session.js'

export const exportPair = async (image, mask) => {
  const body = new FormData()
  body.append('file', image, image.name)
  body.append('mask', JSON.stringify(mask))
  const response = await fetch(`${API_URL}/export/pair`, { method: 'POST', body })
  if (!response.ok) throw new Error(await readError(response, 'Could not export the image and mask.'))
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
  const body = await response.json()
  if (typeof body.id !== 'string' || !body.id) {
    throw new Error('Could not start the export.')
  }
  return body.id
}

const runExport = async (id, files, width, signal, edits) => {
  const body = new FormData()
  if (width != null) body.append('width', String(width))
  body.append('edits', JSON.stringify(files.map((file) => edits.get(file))))
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

const getExport = async (id, signal) => {
  const response = await sessionFetch(`/export/jobs/${id}`, { signal })
  if (!response.ok) {
    throw new Error(await readError(response, 'Could not read export progress.'))
  }
  return response.json()
}

const pollWhilePending = async (work, poll, signal) => {
  const pollController = new AbortController()
  let stopped = false
  let resolveStopped
  const stop = new Promise((resolve) => {
    resolveStopped = resolve
  })
  let cancelWait = null

  const stopPolling = () => {
    if (stopped) return
    stopped = true
    if (cancelWait) cancelWait()
    pollController.abort()
    resolveStopped()
  }
  const handleAbort = () => stopPolling()
  if (signal?.aborted) stopPolling()
  else signal?.addEventListener('abort', handleAbort, { once: true })

  const polling = (async () => {
    while (!stopped) {
      const elapsed = await Promise.race([
        new Promise((resolve) => {
          const timer = setTimeout(
            () => resolve(true),
            EXPORT.progressPollMs,
          )
          cancelWait = () => {
            clearTimeout(timer)
            resolve(false)
          }
        }),
        stop.then(() => false),
      ])
      cancelWait = null
      if (!elapsed || stopped) return

      try {
        await Promise.race([
          poll(pollController.signal),
          stop,
        ])
        if (stopped) return
      } catch (error) {
        if (error?.name === 'AbortError') return
        return
      }
    }
  })()

  try {
    return await work
  } finally {
    stopPolling()
    await polling
    signal?.removeEventListener('abort', handleAbort)
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
  edits = new Map(),
) => {
  let id = null
  let completed = false
  try {
    id = await createExport(files.length, signal)
    const batches = makeExportBatches(files)
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
      for (const batch of batches) {
        await runExport(id, batch, width, signal, edits)
        done += batch.length
        reportProgress(done, files.length)
      }
    })()
    await pollWhilePending(uploads, async (pollSignal) => {
      const state = await getExport(id, pollSignal)
      if (pollSignal.aborted) return
      reportProgress(state.done, state.total)
    }, signal)

    const state = await getExport(id, signal)
    if (state.status !== 'ready') {
      throw new Error(state.error || 'Could not export the images.')
    }
    const blob = await getExportFile(id, signal)
    completed = true
    return blob
  } finally {
    if (id && !completed) await cancelExport(id).catch(() => {})
  }
}
