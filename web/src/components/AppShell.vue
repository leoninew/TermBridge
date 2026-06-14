<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterView, useRouter } from 'vue-router'
import {
  AlertDialogCancel,
  AlertDialogContent,
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
  reorderEnvironmentWorkspaces,
  reorderWorkspaceSessions,
  startSession,
  stopSession,
} from '../api/sessions'
import SessionCreateForm from './SessionCreateForm.vue'
import SessionList from './SessionList.vue'
import { useEnvironmentStore } from '../stores/environment'
import { useToastStore } from '../stores/toast'
import type {
  CreateSessionPayload,
  Session,
  SessionEnvironment,
  ShortcutHost,
} from '../types/sessions'

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
const createSessionContext = ref<{ host?: ShortcutHost; workspace?: string; shortcutId?: string }>(
  {},
)
const deletingSession = ref<Session>()
const deletingWorkspace = ref<{ id: string; path: string }>()
const closeAllDialogOpen = ref(false)
const closingAllSessions = ref(false)
const sidebarCollapsed = ref(false)
const sidebarMinWidth = 280
const sidebarWidth = ref(sidebarMinWidth)
const sidebarMaxWidth = 480
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
    ? sessions.value.filter((session) => session.workspace_id === deletingWorkspace.value?.id)
        .length
    : 0,
)
const openTerminalSessions = computed(() =>
  openTerminalSessionIds.value
    .map((sessionId) => sessions.value.find((session) => session.id === sessionId))
    .filter((session): session is Session => !!session),
)

function errorTitle(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadSessions(), environmentStore.load()])
  } finally {
    loading.value = false
  }
}

async function loadSessions() {
  try {
    applySessionTree((await listSessionTree()).environments)
  } catch (err) {
    const title = errorTitle(err, t('app.errors.loadSessions'))
    if (sessionTree.value.length > 0 || sessions.value.length > 0) {
      toast.show({ title, variant: 'error' })
      return
    }
    error.value = title
  }
}

function applySessionTree(tree: SessionEnvironment[]) {
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
}

function openTerminalSession(session: Session) {
  if (!openTerminalSessionIds.value.includes(session.id)) {
    openTerminalSessionIds.value = [...openTerminalSessionIds.value, session.id]
  }
  activeSessionId.value = session.id
}

function updateCreateSessionContext(context: {
  host?: ShortcutHost
  workspace?: string
  shortcutId?: string
}) {
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
  try {
    const session = await createSession(payload)
    await loadSessions()
    openTerminalSession(session)
    showCreatePanel.value = false
    await router.push('/session')
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.createSession')), variant: 'error' })
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
    toast.show({ title: t('app.success.deleteSession'), variant: 'success' })
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.deleteSession')), variant: 'error' })
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
    toast.show({ title: t('app.success.deleteWorkspace'), variant: 'success' })
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.deleteWorkspace')), variant: 'error' })
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
    toast.show({ title: t('app.success.startSession'), variant: 'success' })
    await router.push('/session')
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.startSession')), variant: 'error' })
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
    toast.show({ title: t('app.success.stopSession'), variant: 'success' })
    await router.push('/session')
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.stopSession')), variant: 'error' })
  }
}

async function handleReorderWorkspaces(payload: { host: ShortcutHost; workspaceIds: string[] }) {
  try {
    applySessionTree(
      (await reorderEnvironmentWorkspaces(payload.host, { workspace_ids: payload.workspaceIds }))
        .environments,
    )
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.loadSessions')), variant: 'error' })
    await loadSessions()
  }
}

async function handleReorderSessions(payload: { workspaceId: string; sessionIds: string[] }) {
  try {
    applySessionTree(
      (await reorderWorkspaceSessions(payload.workspaceId, { session_ids: payload.sessionIds }))
        .environments,
    )
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.loadSessions')), variant: 'error' })
    await loadSessions()
  }
}

function handleReorderTabs(sessionIds: string[]) {
  openTerminalSessionIds.value = sessionIds
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
    toast.show({
      title: t('app.success.closeAllSessions', { count: result.stopped_count }),
      variant: 'success',
    })
    await router.push('/session')
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.closeAllSessions')), variant: 'error' })
  } finally {
    closingAllSessions.value = false
  }
}

async function selectSession(session: Session) {
  openTerminalSession(session)
  showCreatePanel.value = false
  await router.push('/session')
}

async function showCreate(context?: {
  host?: ShortcutHost
  workspace?: string
  shortcutId?: string
}) {
  if (context) {
    createSessionContext.value = {
      ...createSessionContext.value,
      ...context,
    }
  }
  showCreatePanel.value = true
  await router.push('/session')
}

async function navigate(path: string) {
  showCreatePanel.value = false
  await router.push(path)
}

onMounted(() => {
  void refresh()
})
</script>

<template>
  <main
    class="h-screen overflow-hidden bg-slate-100 text-sm text-slate-900 dark:bg-slate-950 dark:text-slate-100"
  >
    <SplitterGroup direction="horizontal" class="flex h-full bg-slate-100 dark:bg-slate-950">
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
          @reorder-workspaces="handleReorderWorkspaces"
          @reorder-sessions="handleReorderSessions"
          @close-all="closeAllDialogOpen = true"
          @navigate="navigate"
        />
      </SplitterPanel>

      <SplitterResizeHandle
        v-if="!sidebarCollapsed"
        :aria-label="t('app.sidebar.resizeLabel')"
        class="group relative hidden w-px cursor-col-resize bg-slate-200/70 outline-none before:absolute before:inset-y-0 before:-left-2 before:-right-2 dark:bg-slate-800 lg:block"
      >
        <span
          class="absolute inset-y-0 left-0 w-px bg-transparent transition group-hover:bg-blue-400 group-focus:bg-blue-500 dark:group-hover:bg-blue-500 dark:group-focus:bg-blue-500"
        />
      </SplitterResizeHandle>

      <SplitterPanel id="main-workspace" :min-size="320" size-unit="px" class="h-full min-h-0">
        <RouterView v-slot="{ Component }">
          <Transition name="main-panel" mode="out-in">
            <section
              v-if="showCreatePanel"
              key="create"
              class="flex h-full min-h-0 overflow-auto bg-slate-100 p-5 dark:bg-slate-950"
            >
              <div
                class="m-auto w-full max-w-3xl border border-slate-200 bg-white/35 p-5 dark:border-slate-800 dark:bg-slate-950"
              >
                <SessionCreateForm
                  :environments="environmentStore.environments"
                  :submitting="creatingSession"
                  :initial-host="createSessionContext.host"
                  :initial-workspace="createSessionContext.workspace"
                  :initial-shortcut-id="createSessionContext.shortcutId"
                  @create="handleCreate"
                  @cancel="showCreatePanel = false"
                />
              </div>
            </section>
            <component
              :is="Component"
              v-else
              :sessions="openTerminalSessions"
              :session="activeSession"
              :starting-session-id="startingSessionId"
              @close="closeTerminalSession"
              @create="showCreate"
              @select="selectSession"
              @start="handleStart"
              @reorder-tabs="handleReorderTabs"
              @create-session="showCreate"
              @environments-updated="environmentStore.update"
            />
          </Transition>
        </RouterView>
      </SplitterPanel>
    </SplitterGroup>

    <button
      v-if="sidebarCollapsed"
      type="button"
      class="fixed bottom-3 left-3 z-40 inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-300/70 bg-slate-100/90 text-slate-600 shadow-lg shadow-blue-900/10 transition hover:bg-white/70 hover:text-blue-700 dark:border-slate-800 dark:bg-slate-900/95 dark:text-slate-400 dark:shadow-none dark:hover:bg-slate-800 dark:hover:text-slate-100"
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
          class="fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border border-slate-200 bg-white p-5 text-sm shadow-xl shadow-blue-900/10 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:shadow-none"
        >
          <div>
            <AlertDialogTitle class="text-lg font-semibold text-slate-950 dark:text-slate-100">{{
              t('app.deleteSession.title')
            }}</AlertDialogTitle>
            <p class="mt-3 text-sm text-slate-600 dark:text-slate-400">
              {{ t('app.deleteSession.description', { name: deletingSession?.name }) }}
            </p>
          </div>
          <div class="flex justify-end gap-2">
            <AlertDialogCancel
              class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
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
          class="fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border border-slate-200 bg-white p-5 text-sm shadow-xl shadow-blue-900/10 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:shadow-none"
        >
          <div>
            <AlertDialogTitle
              class="text-lg font-semibold"
              :class="
                deletingWorkspaceSessionCount > 0
                  ? 'text-amber-700 dark:text-amber-400'
                  : 'text-slate-950 dark:text-slate-100'
              "
            >
              {{ t('app.deleteWorkspace.title') }}
            </AlertDialogTitle>
            <p class="mt-3 text-sm text-slate-600 dark:text-slate-400">
              {{
                t(
                  deletingWorkspaceSessionCount > 0
                    ? 'app.deleteWorkspace.descriptionWithSessions'
                    : 'app.deleteWorkspace.descriptionEmpty',
                  { path: deletingWorkspace?.path, count: deletingWorkspaceSessionCount },
                )
              }}
            </p>
          </div>
          <div class="flex justify-end gap-2">
            <AlertDialogCancel
              class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <button
              type="button"
              class="rounded-lg px-4 py-2 text-white"
              :class="
                deletingWorkspaceSessionCount > 0
                  ? 'bg-amber-600 hover:bg-amber-700'
                  : 'bg-slate-900 hover:bg-slate-800 dark:bg-slate-700 dark:hover:bg-slate-600'
              "
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
          class="fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border border-slate-200 bg-white p-5 text-sm shadow-xl shadow-blue-900/10 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:shadow-none"
        >
          <div>
            <AlertDialogTitle class="text-lg font-semibold text-amber-700 dark:text-amber-400">
              {{ t('app.closeAllSessions.title') }}
            </AlertDialogTitle>
            <p class="mt-3 text-sm text-slate-600 dark:text-slate-400">
              {{ t('app.closeAllSessions.description') }}
            </p>
          </div>
          <div class="flex justify-end gap-2">
            <AlertDialogCancel
              class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
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
