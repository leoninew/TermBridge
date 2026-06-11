<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterView, useRouter } from 'vue-router'
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
import { createSession, deleteSession, listSessionTree, restartSession, stopSession } from '../api/sessions'
import SessionCreateForm from './SessionCreateForm.vue'
import SessionList from './SessionList.vue'
import { useEnvironmentStore } from '../stores/environment'
import { useToastStore } from '../stores/toast'
import type { CreateSessionPayload, Session, SessionEnvironment, ShortcutHost } from '../types/sessions'

const { t } = useI18n()
const router = useRouter()
const environmentStore = useEnvironmentStore()
const toast = useToastStore()
const sessions = ref<Session[]>([])
const sessionTree = ref<SessionEnvironment[]>([])
const activeSessionId = ref<string>()
const openTerminalSessionIds = ref<string[]>([])
const loading = ref(false)
const error = ref('')
const showCreatePanel = ref(false)
const creatingSession = ref(false)
const createError = ref('')
const createSessionContext = ref<{ host?: ShortcutHost; workspace?: string }>({})
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
const openTerminalSessions = computed(() =>
  openTerminalSessionIds.value
    .map((sessionId) => sessions.value.find((session) => session.id === sessionId))
    .filter((session): session is Session => !!session),
)

async function refresh() {
  loading.value = true
  error.value = ''
  await Promise.all([loadSessions(), environmentStore.load()])
  loading.value = false
}

async function loadSessions() {
  try {
    const tree = (await listSessionTree()).environments
    sessionTree.value = tree
    sessions.value = tree.flatMap((environment) =>
      environment.workspaces.flatMap((workspace) => workspace.entries),
    )
    const sessionIds = new Set(sessions.value.map((session) => session.id))
    openTerminalSessionIds.value = openTerminalSessionIds.value.filter((sessionId) =>
      sessionIds.has(sessionId),
    )
    if (activeSessionId.value && !sessionIds.has(activeSessionId.value)) {
      activeSessionId.value = openTerminalSessionIds.value[0]
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.loadSessions')
  }
}

function openTerminalSession(session: Session) {
  if (!openTerminalSessionIds.value.includes(session.id)) {
    openTerminalSessionIds.value = [...openTerminalSessionIds.value, session.id]
  }
  activeSessionId.value = session.id
}

function updateCreateSessionContext(context: { host?: ShortcutHost; workspace?: string }) {
  createSessionContext.value = context
}

function closeTerminalSession(session: Session) {
  const closingIndex = openTerminalSessionIds.value.indexOf(session.id)
  if (closingIndex === -1) {
    return
  }

  const nextOpenIds = openTerminalSessionIds.value.filter((sessionId) => sessionId !== session.id)
  openTerminalSessionIds.value = nextOpenIds
  if (activeSessionId.value === session.id) {
    activeSessionId.value = nextOpenIds[closingIndex] || nextOpenIds[closingIndex - 1]
  }
}

async function handleCreate(payload: CreateSessionPayload) {
  creatingSession.value = true
  createError.value = ''
  try {
    const session = await createSession(payload)
    await loadSessions()
    openTerminalSession(session)
    showCreatePanel.value = false
    await router.push('/session')
  } catch (err) {
    createError.value = err instanceof Error ? err.message : t('app.errors.createSession')
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
    await loadSessions()
    openTerminalSessionIds.value = openTerminalSessionIds.value.filter((id) => id !== sessionId)
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = openTerminalSessionIds.value[0]
    }
    deletingSession.value = undefined
    toast.show(t('app.success.deleteSession'))
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.deleteSession')
  }
}

async function handleRestart(session: Session) {
  error.value = ''
  try {
    const restarted = await restartSession(session.id)
    await loadSessions()
    openTerminalSession(restarted)
    toast.show(t('app.success.restartSession'))
    await router.push('/session')
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.restartSession')
  }
}

async function handleStop(session: Session) {
  error.value = ''
  try {
    const stopped = await stopSession(session.id)
    await loadSessions()
    openTerminalSession(stopped)
    toast.show(t('app.success.stopSession'))
    await router.push('/session')
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.stopSession')
  }
}

async function selectSession(session: Session) {
  openTerminalSession(session)
  showCreatePanel.value = false
  await router.push('/session')
}

async function showCreate() {
  createError.value = ''
  showCreatePanel.value = true
  await router.push('/session')
}

async function navigate(path: string) {
  showCreatePanel.value = false
  createError.value = ''
  await router.push(path)
}

onMounted(() => {
  void refresh()
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
        <SessionList
          class="h-full min-h-0"
          :sessions="sessions"
          :session-tree="sessionTree"
          :active-session-id="activeSessionId"
          :loading="loading"
          :environments-loading="environmentStore.loading"
          :error="error"
          :compact="compactSidebar"
          :environments="environmentStore.environments"
          :has-ready-environment="environmentStore.hasReadyEnvironment"
          @create="showCreate"
          @collapse="sidebarCollapsed = true"
          @create-context="updateCreateSessionContext"
          @select="selectSession"
          @restart="handleRestart"
          @stop="handleStop"
          @remove="askRemove"
          @navigate="navigate"
        />
      </SplitterPanel>

      <SplitterResizeHandle
        v-if="!sidebarCollapsed"
        :aria-label="t('app.sidebar.resizeLabel')"
        class="group hidden w-4 cursor-col-resize items-stretch justify-center outline-none lg:flex"
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
        <Transition name="main-panel" mode="out-in">
          <section
            v-if="showCreatePanel"
            key="create"
            class="flex h-full min-h-0 overflow-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-blue-900/5"
          >
            <div class="m-auto w-full max-w-3xl">
              <SessionCreateForm
                :environments="environmentStore.environments"
                :submitting="creatingSession"
                :error="createError"
                :initial-host="createSessionContext.host"
                :initial-workspace="createSessionContext.workspace"
                @create="handleCreate"
                @cancel="showCreatePanel = false"
              />
            </div>
          </section>
          <RouterView v-else v-slot="{ Component }">
            <component
              :is="Component"
              :sessions="openTerminalSessions"
              :session="activeSession"
              @close="closeTerminalSession"
              @create="showCreate"
              @select="selectSession"
              @restart="handleRestart"
              @environments-updated="environmentStore.update"
            />
          </RouterView>
        </Transition>
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
.main-panel-enter-active,
.main-panel-leave-active {
  transition:
    opacity 160ms ease,
    transform 160ms ease;
}

.main-panel-enter-from,
.main-panel-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
