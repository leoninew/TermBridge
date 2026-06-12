<script setup lang="ts">
import { computed } from 'vue'
import { X } from '@lucide/vue'
import { ToastProvider, ToastRoot, ToastTitle, ToastViewport } from 'reka-ui'
import { useToastStore, type ToastVariant } from '../stores/toast'

const toast = useToastStore()

const toastClasses = computed<Record<ToastVariant, { root: string; close: string }>>(() => ({
  success: {
    root: 'border-emerald-200 bg-emerald-50 text-emerald-900 shadow-emerald-900/10 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200 dark:shadow-none',
    close:
      'text-emerald-700 hover:bg-emerald-100 hover:text-emerald-950 focus:ring-emerald-500 dark:text-emerald-300 dark:hover:bg-emerald-900 dark:hover:text-emerald-100',
  },
  error: {
    root: 'border-red-200 bg-red-50 text-red-900 shadow-red-900/10 dark:border-red-800 dark:bg-red-950 dark:text-red-200 dark:shadow-none',
    close:
      'text-red-700 hover:bg-red-100 hover:text-red-950 focus:ring-red-500 dark:text-red-300 dark:hover:bg-red-900 dark:hover:text-red-100',
  },
}))
</script>

<template>
  <ToastProvider :duration="3000" swipe-direction="right">
    <ToastRoot
      v-for="item in toast.items"
      :key="item.id"
      :open="item.open"
      type="foreground"
      class="relative overflow-hidden rounded-lg border pr-10 text-sm shadow-lg"
      :class="toastClasses[item.variant].root"
      @update:open="toast.updateOpen(item.id, $event)"
    >
      <ToastTitle class="px-4 py-3 font-medium">
        {{ item.title }}
      </ToastTitle>
      <button
        type="button"
        class="absolute right-2 top-2 rounded-md p-1 transition focus:outline-none focus:ring-2"
        :class="toastClasses[item.variant].close"
        aria-label="Close notification"
        @click="toast.updateOpen(item.id, false)"
      >
        <X class="h-4 w-4" />
      </button>
    </ToastRoot>
    <ToastViewport class="fixed bottom-4 right-4 z-50 grid w-80 max-w-[calc(100vw-2rem)] gap-2" />
  </ToastProvider>
</template>
