<script setup lang="ts">
import { Loader2, Monitor, Play, Plus, X } from '@lucide/vue'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Session } from '../types/sessions'

const { t } = useI18n()

const props = defineProps<{
  sessions: Session[]
  session?: Session
  startingSessionId?: string
}>()

const emit = defineEmits<{
  close: [session: Session]
  create: []
  start: [session: Session]
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

function closeTab(event: globalThis.MouseEvent, session: Session) {
  event.preventDefault()
  event.stopPropagation()
  emit('close', session)
}

function isStartingSession(session: Session) {
  return props.startingSessionId === session.id
}
</script>

<template>
  <section class="flex h-full min-h-0 flex-col bg-slate-950 dark:bg-slate-950">
    <TabsRoot
      :model-value="activeTab"
      class="flex min-h-0 flex-1 flex-col"
      @update:model-value="updateActiveTab"
    >
      <div
        class="min-w-0 border-b border-slate-200 bg-slate-100 px-4 text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
      >
        <TabsList class="terminal-tabs-list flex gap-4 overflow-x-auto overflow-y-hidden">
          <TabsTrigger
            v-for="item in sessions"
            :key="item.id"
            :value="item.id"
            class="-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 border-transparent px-1 py-2 text-sm transition hover:text-slate-900 data-[state=active]:border-blue-500 data-[state=active]:text-slate-950 dark:hover:text-slate-100 dark:data-[state=active]:text-slate-100"
          >
            <span>{{ item.name }}</span>
            <button
              type="button"
              class="inline-flex h-4 w-4 items-center justify-center rounded text-slate-400 transition hover:bg-slate-200 hover:text-slate-800 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-100"
              :aria-label="t('session.terminal.closeTab', { name: item.name })"
              :title="t('session.terminal.closeTab', { name: item.name })"
              @click="closeTab($event, item)"
            >
              <X class="h-3 w-3" />
            </button>
          </TabsTrigger>
          <TabsTrigger
            :value="createTabValue"
            class="-mb-px inline-flex shrink-0 items-center border-b-2 border-transparent px-1 py-2 text-sm transition hover:text-slate-900 dark:hover:text-slate-100"
            :aria-label="t('session.terminal.createTab')"
            :title="t('session.terminal.createTab')"
          >
            <Plus class="h-4 w-4" />
          </TabsTrigger>
        </TabsList>
      </div>

      <div
        v-if="!session"
        class="flex min-h-0 flex-1 items-center justify-center bg-slate-950 text-slate-300"
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

      <TabsContent
        v-for="item in sessions"
        :key="item.id"
        :value="item.id"
        class="min-h-0 flex-1 outline-none data-[state=inactive]:hidden"
      >
        <div
          v-if="item.status !== 'running'"
          class="flex h-full min-h-0 items-center justify-center bg-slate-950 text-slate-300"
        >
          <div class="grid justify-items-center gap-3">
            <span>{{
              t('session.terminal.statusUnavailable', { status: t(`session.status.${item.status}`) })
            }}</span>
            <button
              v-if="item.status === 'stopped'"
              type="button"
              :disabled="isStartingSession(item)"
              class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white transition hover:bg-blue-700 disabled:cursor-wait disabled:opacity-70"
              @click="emit('start', item)"
            >
              <Loader2 v-if="isStartingSession(item)" class="h-4 w-4 animate-spin" />
              <Play v-else class="h-4 w-4" />
              {{ t('session.terminal.start') }}
            </button>
          </div>
        </div>
        <div
          v-else-if="!item.url"
          class="flex h-full min-h-0 items-center justify-center bg-slate-950 text-slate-300"
        >
          {{ t('session.terminal.missingUrl') }}
        </div>
        <div v-else class="flex h-full min-h-0 flex-col overflow-hidden bg-slate-950">
          <iframe
            class="flex-1 border-0"
            :src="item.url"
            :title="t('session.terminal.iframeTitle', { name: item.name })"
          />
        </div>
      </TabsContent>
    </TabsRoot>
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
