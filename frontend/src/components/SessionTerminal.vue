<script setup lang="ts">
import { Monitor, Plus, RotateCw, X } from '@lucide/vue'
import { TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Session } from '../types/sessions'

const { t } = useI18n()

const props = defineProps<{
  sessions: Session[]
  session?: Session
}>()

const emit = defineEmits<{
  close: [session: Session]
  create: []
  restart: [session: Session]
  select: [session: Session]
}>()

const activeTab = computed(() => props.session?.id || '')

const createTabValue = '__create_session__'

function updateActiveTab(value: string | number) {
  const tabValue = String(value)
  if (tabValue === createTabValue) {
    emit('create')
    return
  }
  const session = props.sessions.find((item) => item.id === tabValue)
  if (session) {
    emit('select', session)
  }
}

function closeTab(event: MouseEvent, session: Session) {
  event.preventDefault()
  event.stopPropagation()
  emit('close', session)
}
</script>

<template>
  <section
    class="flex h-full min-h-0 flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-xl shadow-blue-900/5"
  >
    <TabsRoot
      :model-value="activeTab"
      class="mb-3 min-w-0"
      @update:model-value="updateActiveTab"
    >
      <TabsList class="terminal-tabs-list flex gap-4 overflow-x-auto overflow-y-hidden border-b border-slate-200">
        <TabsTrigger
          v-for="item in sessions"
          :key="item.id"
          :value="item.id"
          class="-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 border-transparent px-1 py-2 text-sm text-slate-600 transition hover:text-slate-950 data-[state=active]:border-blue-600 data-[state=active]:text-blue-700"
        >
          <span>{{ item.name }}</span>
          <button
            type="button"
            class="inline-flex h-4 w-4 items-center justify-center rounded text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            :aria-label="t('session.terminal.closeTab', { name: item.name })"
            :title="t('session.terminal.closeTab', { name: item.name })"
            @click="closeTab($event, item)"
          >
            <X class="h-3 w-3" />
          </button>
        </TabsTrigger>
        <TabsTrigger
          :value="createTabValue"
          class="-mb-px inline-flex shrink-0 items-center border-b-2 border-transparent px-1 py-2 text-sm text-slate-600 transition hover:text-slate-950"
          :aria-label="t('session.terminal.createTab')"
          :title="t('session.terminal.createTab')"
        >
          <Plus class="h-4 w-4" />
        </TabsTrigger>
      </TabsList>
    </TabsRoot>

    <div
      v-if="!session"
      class="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-slate-950 text-slate-300"
    >
      <div class="grid justify-items-center gap-3 text-sm">
        <Monitor class="h-10 w-10" />
        <span>
          {{ t('session.terminal.emptyPrefix') }}
          <button
            type="button"
            class="text-blue-300 transition hover:text-blue-200"
            @click="emit('create')"
          >
            {{ t('session.terminal.createLink') }}
          </button>
          {{ t('session.terminal.emptySuffix') }}
        </span>
      </div>
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
    <div
      v-else-if="!session.url"
      class="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-slate-950 text-slate-300"
    >
      {{ t('session.terminal.missingUrl') }}
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

<style scoped>
.terminal-tabs-list {
  scrollbar-width: none;
}

.terminal-tabs-list::-webkit-scrollbar {
  display: none;
}
</style>
