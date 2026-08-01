const IMAGE_EXTENSIONS = new Set([
  'bmp',
  'gif',
  'jpeg',
  'jpg',
  'png',
  'tif',
  'tiff',
  'webp',
])

export const IMAGE_FILE_ACCEPT =
  '.bmp,.gif,.jpeg,.jpg,.png,.tif,.tiff,.webp,image/bmp,image/gif,image/jpeg,image/png,image/tiff,image/webp'

const getExtension = (file) => file.name.split('.').pop()?.toLowerCase()

export const getFileKey = (file) =>
  [file.name, file.size, file.lastModified].join(':')

export const filterNewImages = (fileList, existingFiles) => {
  const files = Array.from(fileList ?? [])
  const acceptedFiles = files.filter((file) =>
    IMAGE_EXTENSIONS.has(getExtension(file)),
  )
  const seenFiles = new Set(existingFiles.map(getFileKey))
  const uniqueFiles = acceptedFiles.filter((file) => {
    const key = getFileKey(file)
    if (seenFiles.has(key)) return false

    seenFiles.add(key)
    return true
  })

  return { uniqueFiles }
}

export const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 ** 2).toFixed(1) + ' MB'
}
