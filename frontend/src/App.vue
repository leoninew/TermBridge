<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
  SplitterGroup,
  SplitterPanel,
  SplitterResizeHandle,
} from 'reka-ui'
import { PanelLeftOpen } from '@lucide/vue'
import { createSession, deleteSession, listEnvironments, listSessions, restartSession } from './api/sessions'
import EnvironmentManagement from './components/EnvironmentManagement.vue'
import SessionCreateForm from './components/SessionCreateForm.vue'
import SessionList from './components/SessionList.vue'
import SessionTerminal from './components/SessionTerminal.vue'
import ShortcutManagement from './components/ShortcutManagement.vue'
import type { CreateSessionPayload, EnvironmentSummary, Session } from './types/sessions'

const { t } = useI18n()
const sessions = ref<Session[]>([])
const environments = ref<EnvironmentSummary[]>([])
const activeSessionId = ref<string>()
const loading = ref(false)
const environmentsLoading = ref(false)
const error = ref('')
const showCreatePanel = ref(false)
const creatingSession = ref(false)
const currentPath = ref(window.location.pathname)
const deletingSession = ref<Session>()
const sidebarCollapsed = ref(false)
const sidebarWidth = ref(360)
const sidebarMinWidth = 240
const sidebarMaxWidth = 520
const compactSidebar = computed(() => sidebarWidth.value < 320)
const deleteDialogOpen = computed({
  get: () => !!deletingSession.value,
  set: (open: boolean) => {
    if (!open) {
      deletingSession.value = undefined
    }
  },
})
const activeSession = computed(() =>
  sessions.value.find((session) => session.id === activeSessionId.value),
)
const hasReadyEnvironment = computed(() =>
  environments.value.some((environment) => environment.readiness === 'ready' && environment.available_on_host),
)

async function refresh() {
  loading.value = true
  environmentsLoading.value = true
  error.value = ''
  await Promise.all([loadSessions(), loadEnvironments()])
  loading.value = false
  environmentsLoading.value = false
}

async function loadSessions() {
  try {
    sessions.value = await listSessions()
    if (
      !activeSessionId.value ||
      !sessions.value.some((session) => session.id === activeSessionId.value)
    ) {
      activeSessionId.value = sessions.value[0]?.id
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.loadSessions')
  }
}

async function loadEnvironments() {
  try {
    environments.value = (await listEnvironments()).environments
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.loadEnvironments')
  }
}

function updateEnvironments(nextEnvironments: EnvironmentSummary[]) {
  environments.value = nextEnvironments
}

async function handleCreate(payload: CreateSessionPayload) {
  creatingSession.value = true
  error.value = ''
  try {
    const session = await createSession(payload)
    sessions.value = [session, ...sessions.value]
    activeSessionId.value = session.id
    showCreatePanel.value = false
    navigate('/')
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.createSession')
  } finally {
    creatingSession.value = false
  }
}

function askRemove(session: Session) {
  deletingSession.value = session
}

async function confirmRemove() {
  if (!deletingSession.value) {
    return
  }

  error.value = ''
  const sessionId = deletingSession.value.id
  try {
    await deleteSession(sessionId)
    sessions.value = sessions.value.filter((item) => item.id !== sessionId)
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = sessions.value[0]?.id
    }
    deletingSession.value = undefined
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.deleteSession')
  }
}

async function handleRestart(session: Session) {
  error.value = ''
  try {
    const restarted = await restartSession(session.id)
    sessions.value = sessions.value.map((item) => (item.id === restarted.id ? restarted : item))
    activeSessionId.value = restarted.id
    navigate('/')
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.restartSession')
  }
}

function selectSession(session: Session) {
  activeSessionId.value = session.id
  navigate('/')
}

function showCreate() {
  sidebarCollapsed.value = false
  showCreatePanel.value = true
}

function navigate(path: string) {
  window.history.pushState({}, '', path)
  currentPath.value = path
  if (path === '/') {
    void loadEnvironments()
  }
}

function handlePopState() {
  currentPath.value = window.location.pathname
}

onMounted(() => {
  window.addEventListener('popstate', handlePopState)
  void refresh()
})

onUnmounted(() => {
  window.removeEventListener('popstate', handlePopState)
})
</script>

<template>
  <main class="h-screen overflow-hidden bg-slate-100 p-4 text-sm text-slate-900 md:p-5">
    <SplitterGroup direction="horizontal" class="flex h-full">
      <SplitterPanel
        v-if="!sidebarCollapsed"
        id="session-sidebar"
        :default-size="sidebarWidth"
        :min-size="sidebarMinWidth"
        :max-size="sidebarMaxWidth"
        size-unit="px"
        class="relative h-full min-h-0"
        @resize="sidebarWidth = $event"
      >
        <Transition name="sidebar-panel" mode="out-in">
          <SessionCreateForm
            v-if="showCreatePanel"
            key="create"
            class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-blue-900/5"
            :environments="environments"
            :submitting="creatingSession"
            @create="handleCreate"
            @cancel="showCreatePanel = false"
          />
          <SessionList
            v-else
            key="list"
            class="h-full min-h-0"
            :sessions="sessions"
            :active-session-id="activeSessionId"
            :loading="loading"
            :environments-loading="environmentsLoading"
            :error="error"
            :compact="compactSidebar"
            :environments="environments"
            :has-ready-environment="hasReadyEnvironment"
            @create="showCreate"
            @collapse="sidebarCollapsed = true"
            @select="selectSession"
            @restart="handleRestart"
            @remove="askRemove"
            @navigate="navigate"
          />
        </Transition>
      </SplitterPanel>

      <SplitterResizeHandle
        v-if="!sidebarCollapsed"
        :aria-label="t('app.sidebar.resizeLabel')"
        class="group hidden w-4 cursor-col-resize items-stretch justify-center outline-none focus:ring-4 focus:ring-blue-100 lg:flex"
      >
        <span
          class="my-2 w-px rounded-full bg-slate-200 transition group-hover:w-1 group-hover:bg-blue-300 group-focus:w-1 group-focus:bg-blue-500"
        />
      </SplitterResizeHandle>

      <SplitterPanel id="main-workspace" :min-size="320" size-unit="px" class="h-full min-h-0">
        <div v-if="sidebarCollapsed" class="mb-3 flex justify-start">
          <button
            type="button"
            class="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-300 bg-white text-slate-600 shadow-lg shadow-blue-900/10 transition hover:bg-slate-50"
            :aria-label="t('app.sidebar.expandLabel')"
            :title="t('app.sidebar.expandLabel')"
            @click="sidebarCollapsed = false"
          >
            <PanelLeftOpen class="h-4 w-4" />
          </button>
        </div>
        <EnvironmentManagement v-if="currentPath === '/environment'" @environments-updated="updateEnvironments" />
        <ShortcutManagement v-else-if="currentPath === '/shortcuts'" :sessions="sessions" />
        <SessionTerminal v-else :session="activeSession" @restart="handleRestart" />
      </SplitterPanel>
    </SplitterGroup>

    <AlertDialogRoot v-model:open="deleteDialogOpen">
      <AlertDialogPortal>
        <AlertDialogOverlay class="fixed inset-0 z-50 bg-slate-950/40" />
        <AlertDialogContent
          class="fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-2xl bg-white p-5 text-sm shadow-2xl"
        >
          <div>
            <AlertDialogTitle class="text-lg font-semibold text-slate-950">{{
              t('app.deleteSession.title')
            }}</AlertDialogTitle>
            <AlertDialogDescription class="mt-2 text-sm text-slate-600">
              {{ t('app.deleteSession.description', { name: deletingSession?.name }) }}
            </AlertDialogDescription>
          </div>
          <div class="flex justify-end gap-2">
            <AlertDialogCancel class="rounded-lg border border-slate-300 px-4 py-2">
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <button
              type="button"
              class="rounded-lg bg-red-600 px-4 py-2 text-white"
              @click="confirmRemove"
            >
              {{ t('app.actions.delete') }}
            </button>
          </div>
        </AlertDialogContent>
      </AlertDialogPortal>
    </AlertDialogRoot>
  </main>
</template>

<style scoped>
.sidebar-panel-enter-active,
.sidebar-panel-leave-active,
.sidebar-rail-enter-active,
.sidebar-rail-leave-active {
  transition:
    opacity 160ms ease,
    transform 160ms ease;
}

.sidebar-panel-enter-from,
.sidebar-panel-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

.sidebar-rail-enter-from,
.sidebar-rail-leave-to {
  opacity: 0;
  transform: translateX(-6px);
}
</style>
