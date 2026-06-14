<script setup lang="ts">
import { Ban, Loader2, Play, Trash2, Unplug } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Session } from '../types/sessions'

const { t } = useI18n()

const props = defineProps<{
  session: Session
  active: boolean
  compact?: boolean
  starting?: boolean
}>()

const emit = defineEmits<{
  select: [session: Session]
  start: [session: Session]
  stop: [session: Session]
  remove: [session: Session]
}>()

const statusClass: Record<Session['status'], string> = {
  running: 'bg-emerald-100 text-emerald-700',
  starting: 'bg-blue-100 text-blue-700',
  disconnected: 'bg-amber-100 text-amber-700',
  stopped: 'bg-slate-200 text-slate-700',
  failed: 'bg-red-100 text-red-700',
}
const shortcutLabel = computed(() => {
  const name = props.session.shortcut_name || props.session.runtime
  return props.session.host ? `${t(`hosts.${props.session.host}`)} · ${name}` : name
})

function requestRemove() {
  emit('remove', props.session)
}
</script>

<template>
  <article
    class="group relative rounded-xl border p-3 pr-20 shadow-md shadow-blue-900/5 transition-shadow hover:shadow-xl hover:shadow-blue-900/10"
    :class="active ? 'border-blue-500 shadow-xl shadow-blue-900/10' : 'border-slate-200'"
  >
    <button
      type="button"
      class="grid w-full gap-1.5 text-left"
      @click="emit('select', props.session)"
    >
      <span class="flex min-w-0 items-center gap-2">
        <span class="truncate text-sm font-semibold text-slate-950">{{ session.name }}</span>
        <span
          class="shrink-0 rounded-full px-2 py-0.5 text-sm"
          :class="statusClass[session.status]"
        >
          {{ t(`session.status.${session.status}`) }}
        </span>
      </span>
      <span class="truncate text-sm text-slate-500">{{ session.workspace }}</span>
      <span v-if="!compact" class="flex items-center gap-3 text-sm text-slate-500">
        <span>{{ t('session.card.shortcut', { shortcut: shortcutLabel }) }}</span>
      </span>
    </button>
    <div class="absolute right-3 top-3 z-10 flex gap-1">
      <button
        v-if="session.status === 'running'"
        type="button"
        class="relative inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 opacity-0 transition hover:bg-amber-50 hover:text-amber-600 group-hover:opacity-100 group-focus-within:opacity-100"
        :aria-label="t('session.card.stopLabel')"
        :title="t('session.card.stopLabel')"
        @click.stop="emit('stop', session)"
      >
        <Ban class="h-4 w-4" />
      </button>
      <span
        v-if="session.status === 'disconnected'"
        class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-amber-500"
        :aria-label="t('session.status.disconnected')"
        :title="t('session.status.disconnected')"
      >
        <Unplug class="h-4 w-4" />
      </span>
      <button
        v-if="session.status === 'stopped' || session.status === 'disconnected'"
        type="button"
        :disabled="starting"
        class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-blue-50 hover:text-blue-600 disabled:cursor-wait disabled:opacity-60"
        :aria-label="t('session.card.startLabel')"
        :title="t('session.card.startLabel')"
        @click.stop="emit('start', session)"
      >
        <Loader2 v-if="starting" class="h-4 w-4 animate-spin" />
        <Play v-else class="h-4 w-4" />
      </button>
      <button
        type="button"
        class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 group-focus-within:opacity-100"
        :aria-label="t('session.card.deleteLabel')"
        :title="t('session.card.deleteLabel')"
        @click.stop="requestRemove"
      >
        <Trash2 class="h-4 w-4" />
      </button>
    </div>
  </article>
</template>
