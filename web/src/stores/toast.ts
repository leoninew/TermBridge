import { ref } from 'vue'
import { defineStore } from 'pinia'

export type ToastVariant = 'success' | 'error'

const DEFAULT_TOAST_DURATION_MS = 5000
const TOAST_REMOVE_DELAY_MS = 200

type ToastOptions = {
  title: string
  variant?: ToastVariant
  duration?: number
}

type ToastItem = {
  id: number
  title: string
  variant: ToastVariant
  open: boolean
}

export const useToastStore = defineStore('toast', () => {
  const items = ref<ToastItem[]>([])
  const closeTimers = new Map<number, number>()
  const removeTimers = new Map<number, number>()
  let nextId = 1

  function clearCloseTimer(id: number) {
    const timer = closeTimers.get(id)
    if (timer !== undefined) {
      window.clearTimeout(timer)
      closeTimers.delete(id)
    }
  }

  function clearRemoveTimer(id: number) {
    const timer = removeTimers.get(id)
    if (timer !== undefined) {
      window.clearTimeout(timer)
      removeTimers.delete(id)
    }
  }

  function remove(id: number) {
    clearCloseTimer(id)
    clearRemoveTimer(id)
    items.value = items.value.filter((toast) => toast.id !== id)
  }

  function scheduleClose(id: number, duration: number) {
    clearCloseTimer(id)
    if (duration <= 0 || duration === Number.POSITIVE_INFINITY) {
      return
    }
    closeTimers.set(
      id,
      window.setTimeout(() => {
        closeTimers.delete(id)
        updateOpen(id, false)
      }, duration),
    )
  }

  function show(options: ToastOptions) {
    const id = nextId++
    items.value = [
      ...items.value,
      { id, title: options.title, variant: options.variant ?? 'success', open: true },
    ]
    scheduleClose(id, options.duration ?? DEFAULT_TOAST_DURATION_MS)
  }

  function updateOpen(id: number, open: boolean) {
    const item = items.value.find((toast) => toast.id === id)
    if (!item) {
      return
    }

    item.open = open
    if (!open) {
      clearCloseTimer(id)
      clearRemoveTimer(id)
      removeTimers.set(id, window.setTimeout(() => remove(id), TOAST_REMOVE_DELAY_MS))
    }
  }

  return { items, show, updateOpen }
})
