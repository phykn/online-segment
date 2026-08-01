export class ResultCache {
  constructor() {
    this.items = new WeakMap()
  }

  get(image, width, revision) {
    const result = this.items.get(image)
    return isCurrent(result, image, width, revision) ? result : null
  }

  set(image, width, revision, value) {
    const result = { image, width, revision, ...value }
    this.items.set(image, result)
    return result
  }

  delete(image) {
    this.items.delete(image)
  }

  clear() {
    this.items = new WeakMap()
  }
}

export const isCurrent = (result, image, width, revision) =>
  result?.image === image &&
  result.width === width &&
  result.revision === revision
