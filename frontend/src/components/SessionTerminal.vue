<script setup lang="ts">
import { Monitor, RotateCw } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import type { Session } from '../types/sessions'

const { t } = useI18n()

defineProps<{
  session?: Session
}>()

const emit = defineEmits<{
  restart: [session: Session]
}>()
</script>

<template>
  <section
    class="flex h-full min-h-0 flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-xl shadow-blue-900/5"
  >
    <div class="mb-3 min-w-0">
      <div class="flex min-w-0 items-baseline gap-3">
        <h2 class="shrink-0 text-lg font-semibold text-slate-950">
          {{ t('session.terminal.title') }}
        </h2>
        <p v-if="session" class="min-w-0 truncate text-sm text-slate-500">
          {{ session.name }} · {{ session.workspace }}
        </p>
      </div>
    </div>

    <div
      v-if="!session"
      class="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-slate-950 text-slate-300"
    >
      <div class="grid justify-items-center gap-3">
        <Monitor class="h-10 w-10" />
        <span>{{ t('session.terminal.empty') }}</span>
      </div>
    </div>
    <div
      v-else-if="!session.url"
      class="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-slate-950 text-slate-300"
    >
      {{ t('session.terminal.missingUrl') }}
    </div>
    <div
      v-else-if="session.status !== 'running'"
      class="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-slate-950 text-slate-300"
    >
      <div class="grid justify-items-center gap-3">
        <span>{{
          t('session.terminal.statusUnavailable', { status: t(`session.status.${session.status}`) })
        }}</span>
        <button
          v-if="session.status === 'stopped'"
          type="button"
          class="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm text-white transition hover:bg-blue-700"
          @click="emit('restart', session)"
        >
          <RotateCw class="h-4 w-4" />
          {{ t('session.terminal.restart') }}
        </button>
      </div>
    </div>
    <div v-else class="flex min-h-0 flex-1 flex-col overflow-hidden bg-slate-950">
      <iframe
        class="flex-1 border-0"
        sandbox="allow-scripts allow-same-origin"
        :src="session.url"
        :title="t('session.terminal.iframeTitle', { name: session.name })"
      />
    </div>
  </section>
</template>
