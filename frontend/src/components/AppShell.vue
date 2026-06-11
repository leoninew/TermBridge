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
import {
  closeAllSessions,
  createSession,
  deleteSession,
  deleteSessionWorkspace,
  listSessionTree,
  startSession,
  stopSession,
} from '../api/sessions'
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
const startingSessionId = ref<string>()
const createError = ref('')
const createSessionContext = ref<{ host?: ShortcutHost; workspace?: string }>({})
const deletingSession = ref<Session>()
const deletingWorkspace = ref<{ id: string; path: string }>()
const closeAllDialogOpen = ref(false)
const closingAllSessions = ref(false)
const sidebarCollapsed = ref(false)
const sidebarMinWidth = 400
const sidebarWidth = ref(400)
const sidebarMaxWidth = 560
const compactSidebar = computed(() => sidebarWidth.value < 360)
const deleteDialogOpen = computed({
  get: () => !!deletingSession.value,
  set: (open: boolean) => {
    if (!open) {
      deletingSession.value = undefined
    }
  },
})
const deleteWorkspaceDialogOpen = computed({
  get: () => !!deletingWorkspace.value,
  set: (open: boolean) => {
    if (!open) {
      deletingWorkspace.value = undefined
    }
  },
})
const activeSession = computed(() =>
  sessions.value.find((session) => session.id === activeSessionId.value),
)
const deletingWorkspaceSessionCount = computed(() =>
  deletingWorkspace.value
    ? sessions.value.filter((session) => session.workspace_id === deletingWorkspace.value?.id).length
    : 0,
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

function askRemoveWorkspace(workspace: { id: string; path: string }) {
  deletingWorkspace.value = workspace
}

async function confirmRemoveWorkspace() {
  if (!deletingWorkspace.value) {
    return
  }

  error.value = ''
  const workspaceId = deletingWorkspace.value.id
  const deletedSessionIds = sessions.value
    .filter((session) => session.workspace_id === workspaceId)
    .map((session) => session.id)
  try {
    await deleteSessionWorkspace(workspaceId)
    await loadSessions()
    openTerminalSessionIds.value = openTerminalSessionIds.value.filter(
      (id) => !deletedSessionIds.includes(id),
    )
    if (activeSessionId.value && deletedSessionIds.includes(activeSessionId.value)) {
      activeSessionId.value = openTerminalSessionIds.value[0]
    }
    deletingWorkspace.value = undefined
    toast.show(t('app.success.deleteWorkspace'))
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.deleteWorkspace')
  }
}

async function handleStart(session: Session) {
  if (startingSessionId.value) {
    return
  }

  error.value = ''
  startingSessionId.value = session.id
  try {
    const started = await startSession(session.id)
    await loadSessions()
    openTerminalSession(started)
    toast.show(t('app.success.startSession'))
    await router.push('/session')
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.startSession')
  } finally {
    startingSessionId.value = undefined
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

async function confirmCloseAllSessions() {
  error.value = ''
  closingAllSessions.value = true
  try {
    const result = await closeAllSessions()
    await loadSessions()
    openTerminalSessionIds.value = []
    activeSessionId.value = undefined
    closeAllDialogOpen.value = false
    toast.show(t('app.success.closeAllSessions', { count: result.stopped_count }))
    await router.push('/session')
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('app.errors.closeAllSessions')
  } finally {
    closingAllSessions.value = false
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
          :starting-session-id="startingSessionId"
          @create="showCreate"
          @collapse="sidebarCollapsed = true"
          @create-context="updateCreateSessionContext"
          @select="selectSession"
          @start="handleStart"
          @stop="handleStop"
          @remove="askRemove"
          @remove-workspace="askRemoveWorkspace"
          @close-all="closeAllDialogOpen = true"
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
              :starting-session-id="startingSessionId"
              @close="closeTerminalSession"
              @create="showCreate"
              @select="selectSession"
              @start="handleStart"
              @environments-updated="environmentStore.update"
            />
          </RouterView>
        </Transition>
      </SplitterPanel>
    </SplitterGroup>

    <button
      v-if="sidebarCollapsed"
      type="button"
      class="fixed left-1 top-1 z-40 inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-xl shadow-blue-900/15 transition hover:bg-blue-50 hover:text-blue-700"
      :aria-label="t('app.sidebar.expandLabel')"
      :title="t('app.sidebar.expandLabel')"
      @click="sidebarCollapsed = false"
    >
      <PanelLeftOpen class="h-5 w-5" />
    </button>

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

    <AlertDialogRoot v-model:open="deleteWorkspaceDialogOpen">
      <AlertDialogPortal>
        <AlertDialogOverlay class="fixed inset-0 z-50 bg-slate-950/40" />
        <AlertDialogContent
          class="fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-2xl bg-white p-5 text-sm shadow-2xl"
        >
          <div>
            <AlertDialogTitle
              class="text-lg font-semibold"
              :class="deletingWorkspaceSessionCount > 0 ? 'text-amber-700' : 'text-slate-950'"
            >
              {{ t('app.deleteWorkspace.title') }}
            </AlertDialogTitle>
            <AlertDialogDescription class="mt-2 text-sm text-slate-600">
              {{
                t(
                  deletingWorkspaceSessionCount > 0
                    ? 'app.deleteWorkspace.descriptionWithSessions'
                    : 'app.deleteWorkspace.descriptionEmpty',
                  { path: deletingWorkspace?.path, count: deletingWorkspaceSessionCount },
                )
              }}
            </AlertDialogDescription>
          </div>
          <div class="flex justify-end gap-2">
            <AlertDialogCancel class="rounded-lg border border-slate-300 px-4 py-2">
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <button
              type="button"
              class="rounded-lg px-4 py-2 text-white"
              :class="deletingWorkspaceSessionCount > 0 ? 'bg-amber-600' : 'bg-slate-900'"
              @click="confirmRemoveWorkspace"
            >
              {{ t('app.deleteWorkspace.confirm') }}
            </button>
          </div>
        </AlertDialogContent>
      </AlertDialogPortal>
    </AlertDialogRoot>

    <AlertDialogRoot v-model:open="closeAllDialogOpen">
      <AlertDialogPortal>
        <AlertDialogOverlay class="fixed inset-0 z-50 bg-slate-950/40" />
        <AlertDialogContent
          class="fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-2xl bg-white p-5 text-sm shadow-2xl"
        >
          <div>
            <AlertDialogTitle class="text-lg font-semibold text-amber-700">
              {{ t('app.closeAllSessions.title') }}
            </AlertDialogTitle>
            <AlertDialogDescription class="mt-2 text-sm text-slate-600">
              {{ t('app.closeAllSessions.description') }}
            </AlertDialogDescription>
          </div>
          <div class="flex justify-end gap-2">
            <AlertDialogCancel class="rounded-lg border border-slate-300 px-4 py-2">
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <button
              type="button"
              :disabled="closingAllSessions"
              class="rounded-lg bg-amber-600 px-4 py-2 text-white disabled:opacity-60"
              @click="confirmCloseAllSessions"
            >
              {{ t('app.closeAllSessions.confirm') }}
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
