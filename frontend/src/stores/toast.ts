import { ref } from 'vue'
import { defineStore } from 'pinia'

type ToastItem = {
  id: number
  title: string
  open: boolean
}

export const useToastStore = defineStore('toast', () => {
  const items = ref<ToastItem[]>([])
  let nextId = 1

  function show(title: string) {
    items.value = [...items.value, { id: nextId++, title, open: true }]
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
