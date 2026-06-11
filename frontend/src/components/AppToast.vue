<script setup lang="ts">
import { X } from '@lucide/vue'
import { ToastProvider, ToastRoot, ToastTitle, ToastViewport } from 'reka-ui'
import { useToastStore } from '../stores/toast'

const toast = useToastStore()
</script>

<template>
  <ToastProvider :duration="3000" swipe-direction="right">
    <ToastRoot
      v-for="item in toast.items"
      :key="item.id"
      :open="item.open"
      type="foreground"
      class="relative overflow-hidden rounded-xl border border-blue-200 bg-blue-50 pr-10 text-sm text-blue-900 shadow-xl shadow-blue-900/10"
      @update:open="toast.updateOpen(item.id, $event)"
    >
      <ToastTitle class="px-4 py-3 font-medium">
        {{ item.title }}
      </ToastTitle>
      <button
        type="button"
        class="absolute right-2 top-2 rounded-md p-1 text-blue-700 transition hover:bg-blue-100 hover:text-blue-950 focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-label="Close notification"
        @click="toast.updateOpen(item.id, false)"
      >
        <X class="h-4 w-4" />
      </button>
    </ToastRoot>
    <ToastViewport class="fixed bottom-4 right-4 z-50 grid w-80 max-w-[calc(100vw-2rem)] gap-2" />
  </ToastProvider>
</template>
