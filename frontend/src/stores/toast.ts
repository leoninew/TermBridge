import { ref } from 'vue'
import { defineStore } from 'pinia'

export type ToastVariant = 'success' | 'error'

type ToastOptions = {
  title: string
  variant?: ToastVariant
}

type ToastItem = {
  id: number
  title: string
  variant: ToastVariant
  open: boolean
}

export const useToastStore = defineStore('toast', () => {
  const items = ref<ToastItem[]>([])
  let nextId = 1

  function show(options: ToastOptions) {
    items.value = [
      ...items.value,
      { id: nextId++, title: options.title, variant: options.variant ?? 'success', open: true },
    ]
  }

  function updateOpen(id: number, open: boolean) {
    const item = items.value.find((toast) => toast.id === id)
    if (item) {
      item.open = open
    }
    if (!open) {
      window.setTimeout(() => {
        items.value = items.value.filter((toast) => toast.id !== id)
      }, 200)
    }
  }

  return { items, show, updateOpen }
})
