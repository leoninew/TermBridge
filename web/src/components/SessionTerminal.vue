<script setup lang="ts">
import { Loader2, Monitor, Play, Plus, SquareTerminal, X } from '@lucide/vue'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { computed, ref, watch } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { useI18n } from 'vue-i18n'
import CygwinLogo from './CygwinLogo.vue'
import LinuxLogo from './LinuxLogo.vue'
import WslLogo from './WslLogo.vue'
import { useThemeStore } from '../stores/theme'
import type { Session, ShortcutHost } from '../types/sessions'

type DragEndEvent = {
  oldIndex?: number
  newIndex?: number
  from: globalThis.HTMLElement
  to: globalThis.HTMLElement
  item: globalThis.HTMLElement
}

const { t } = useI18n()
const themeStore = useThemeStore()

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
  reorderTabs: [sessionIds: string[]]
}>()

const orderedTabs = ref<Session[]>([])
const activeTab = computed(() => props.session?.id || '')
const activeShortcutLabel = computed(
  () => props.session?.shortcut_name || props.session?.runtime || '',
)

const createTabValue = '__create_session__'

function terminalUrl(url: string) {
  const [baseUrl, hash = ''] = url.split('#', 2)
  const [path, query = ''] = baseUrl.split('?', 2)
  const searchParams = new globalThis.URLSearchParams(query)
  searchParams.set('theme', themeStore.mode)
  const themedUrl = `${path}?${searchParams.toString()}`
  return hash ? `${themedUrl}#${hash}` : themedUrl
}

watch(
  () => props.sessions,
  (sessions) => {
    const sessionById = new Map(sessions.map((session) => [session.id, session]))
    const orderedSessionIds = orderedTabs.value.map((session) => session.id)
    orderedTabs.value = [
      ...orderedSessionIds
        .map((sessionId) => sessionById.get(sessionId))
        .filter((session): session is Session => !!session),
      ...sessions.filter((session) => !orderedSessionIds.includes(session.id)),
    ]
  },
  { immediate: true },
)

function hasDragged(event: DragEndEvent) {
  return event.oldIndex !== undefined && event.newIndex !== undefined && event.oldIndex !== event.newIndex
}

function handleTabReorder(event: DragEndEvent) {
  if (!hasDragged(event)) {
    return
  }
  emit(
    'reorderTabs',
    orderedTabs.value.map((session) => session.id),
  )
}

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

function environmentLogo(host: ShortcutHost | null | undefined) {
  if (host === 'windows_cygwin') {
    return CygwinLogo
  }
  if (host === 'windows_wsl') {
    return WslLogo
  }
  if (host === 'linux') {
    return LinuxLogo
  }
  return SquareTerminal
}
</script>

<template>
  <section class="flex h-full min-h-0 flex-col bg-slate-950 opacity-90 dark:bg-slate-950">
    <TabsRoot
      :model-value="activeTab"
      class="flex min-h-0 flex-1 flex-col"
      @update:model-value="updateActiveTab"
    >
      <div
        class="h-11 min-w-0 border-b border-slate-200 bg-slate-100 px-3 text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
      >
        <TabsList
          class="terminal-tabs-list flex h-full items-center gap-3 overflow-x-auto overflow-y-hidden"
        >
          <VueDraggable
            v-model="orderedTabs"
            ghost-class="opacity-60"
            filter=".tab-action"
            :prevent-on-filter="false"
            class="flex h-full items-center gap-3"
            @end="handleTabReorder"
          >
            <TabsTrigger
              v-for="item in orderedTabs"
              :key="item.id"
              :value="item.id"
              class="inline-flex h-8 max-w-64 shrink-0 items-center gap-2 bg-transparent px-2 text-sm transition hover:text-slate-900 data-[state=active]:font-medium data-[state=active]:text-slate-950 dark:hover:text-slate-100 dark:data-[state=active]:text-slate-100"
              :title="item.workspace"
            >
                <component :is="environmentLogo(item.host)" class="h-4 w-4 shrink-0" />
                <span class="truncate">{{ item.name }}</span>
                <button
                  type="button"
                  class="tab-action inline-flex h-4 w-4 shrink-0 items-center justify-center rounded text-slate-400 transition hover:bg-slate-200 hover:text-slate-800 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                  :aria-label="t('session.terminal.closeTab', { name: item.name })"
                  :title="t('session.terminal.closeTab', { name: item.name })"
                  @click="closeTab($event, item)"
                >
                  <X class="h-3 w-3" />
                </button>
            </TabsTrigger>
          </VueDraggable>
          <TabsTrigger
            :value="createTabValue"
            class="inline-flex h-8 shrink-0 items-center justify-center bg-transparent px-2 text-sm text-slate-400 transition hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200"
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
              t('session.terminal.statusUnavailable', {
                status: t(`session.status.${item.status}`),
              })
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
            :src="terminalUrl(item.url)"
            :title="t('session.terminal.iframeTitle', { name: item.name })"
          />
        </div>
      </TabsContent>
    </TabsRoot>

    <div
      class="flex h-7 shrink-0 items-center gap-3 border-t border-slate-200/70 bg-slate-100 px-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-500"
    >
      <span
        v-if="session"
        class="inline-flex min-w-0 items-center gap-1"
        :title="session.workspace"
      >
        <span class="shrink-0">{{ t('session.create.workspace') }}:</span>
        <span class="min-w-0 truncate text-slate-600 dark:text-slate-400">{{
          session.workspace
        }}</span>
      </span>
      <span
        v-if="activeShortcutLabel"
        class="inline-flex shrink-0 items-center gap-1"
        :title="activeShortcutLabel"
      >
        <span>{{ t('session.create.shortcut') }}:</span>
        <span class="text-slate-600 dark:text-slate-400">{{ activeShortcutLabel }}</span>
      </span>
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
