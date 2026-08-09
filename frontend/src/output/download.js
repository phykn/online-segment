export const pngName = (image) => {
  const dot = image.name.lastIndexOf('.')
  const name = dot > 0 ? image.name.slice(0, dot) : image.name
  return `${name}.png`
}

export const zipName = (value) => {
  const requested = String(value ?? '').trim().replace(/\.zip$/i, '')
  const safe = requested
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
    .replace(/[. ]+$/g, '')
  return `${safe || 'masks'}.zip`
}

export const saveBlob = (blob, name) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
