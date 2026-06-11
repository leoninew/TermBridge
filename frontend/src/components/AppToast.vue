<script setup lang="ts">
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
      class="overflow-hidden rounded-xl border border-blue-200 bg-blue-50 text-sm text-blue-900 shadow-xl shadow-blue-900/10"
      @update:open="toast.updateOpen(item.id, $event)"
    >
      <ToastTitle class="border-l-4 border-blue-600 px-4 py-3 font-medium">
        {{ item.title }}
      </ToastTitle>
    </ToastRoot>
    <ToastViewport class="fixed right-4 top-4 z-50 grid w-80 max-w-[calc(100vw-2rem)] gap-2" />
  </ToastProvider>
</template>
