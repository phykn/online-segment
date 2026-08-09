export const estimateRemainingSeconds = (elapsedMs, progress) => {
  if (
    !Number.isFinite(elapsedMs) ||
    elapsedMs < 0 ||
    !Number.isFinite(progress) ||
    progress <= 0
  ) {
    return null
  }
  if (progress >= 100) return 0

  return Math.max(
    0,
    Math.ceil((elapsedMs / 1000) * ((100 - progress) / progress)),
  )
}

export const formatRemainingTime = (seconds) => {
  if (!Number.isFinite(seconds) || seconds < 0) return '--:--'

  const total = Math.ceil(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remainder = total % 60
  const paddedMinutes = String(minutes).padStart(2, '0')
  const paddedSeconds = String(remainder).padStart(2, '0')

  return hours > 0
    ? `${hours}:${paddedMinutes}:${paddedSeconds}`
    : `${paddedMinutes}:${paddedSeconds}`
}

export const formatDownloadStatus = (progress, remainingSeconds) =>
  `${progress}% · ${formatRemainingTime(remainingSeconds)}`

