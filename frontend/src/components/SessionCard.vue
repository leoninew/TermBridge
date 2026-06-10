<script setup lang="ts">
import { RotateCw, Trash2 } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import type { Session } from '../types/sessions'

const { t } = useI18n()

const props = defineProps<{
  session: Session
  active: boolean
  compact?: boolean
}>()

const emit = defineEmits<{
  select: [session: Session]
  restart: [session: Session]
  remove: [session: Session]
}>()

const statusClass: Record<Session['status'], string> = {
  running: 'bg-emerald-100 text-emerald-700',
  starting: 'bg-blue-100 text-blue-700',
  stopped: 'bg-slate-200 text-slate-700',
  failed: 'bg-red-100 text-red-700',
}

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
        <span>{{
          t('session.card.shortcut', { shortcut: session.shortcut_name || session.runtime })
        }}</span>
      </span>
    </button>
    <div class="absolute right-3 top-3 z-10 flex gap-1">
      <button
        v-if="session.status === 'stopped'"
        type="button"
        class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-blue-50 hover:text-blue-600"
        :aria-label="t('session.card.restartLabel')"
        :title="t('session.card.restartLabel')"
        @click.stop="emit('restart', session)"
      >
        <RotateCw class="h-4 w-4" />
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
