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
import { Loader2, PanelLeftOpen } from '@lucide/vue'
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
import { workspaceDisplayLabelsById } from '../sessionTreeLabels'
import { useEnvironmentStore } from '../stores/environment'
import { useToastStore } from '../stores/toast'
import type {
  CreateSessionPayload,
  Session,
  SessionEnvironment,
  SessionStatus,
  SessionWorkspace,
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
const initialSessionTreeLoading = ref(false)
const sessionStatusRefreshing = ref(false)
const sessionRuntimeStateVerified = ref(false)
const freshTerminalSessionIds = ref<string[]>([])
const error = ref('')
const showCreatePanel = ref(false)
const creatingSession = ref(false)
const startingSessionId = ref<string>()
const stoppingSessionId = ref<string>()
const createSessionContext = ref<{ host?: ShortcutHost; workspace?: string; shortcutId?: string }>(
  {},
)
const deletingSession = ref<Session>()
const deletingSessionId = ref<string>()
const deletingWorkspace = ref<{ id: string; path: string }>()
const deletingWorkspaceId = ref<string>()
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
    if (!open && !deletingSessionId.value) {
      deletingSession.value = undefined
    }
  },
})
const deleteWorkspaceDialogOpen = computed({
  get: () => !!deletingWorkspace.value,
  set: (open: boolean) => {
    if (!open && !deletingWorkspaceId.value) {
      deletingWorkspace.value = undefined
    }
  },
})
const terminalRuntimeAvailableSessionIds = computed(() =>
  sessionRuntimeStateVerified.value
    ? openTerminalSessionIds.value
    : openTerminalSessionIds.value.filter((sessionId) =>
        freshTerminalSessionIds.value.includes(sessionId),
      ),
)
const terminalRuntimeAvailableSessionIdSet = computed(
  () => new Set(terminalRuntimeAvailableSessionIds.value),
)
const terminalActiveSessionId = computed(() =>
  activeSessionId.value && terminalRuntimeAvailableSessionIdSet.value.has(activeSessionId.value)
    ? activeSessionId.value
    : terminalRuntimeAvailableSessionIds.value[0],
)
const terminalActiveSession = computed(() =>
  sessions.value.find((session) => session.id === terminalActiveSessionId.value),
)
const deletingWorkspaceSessionCount = computed(() =>
  deletingWorkspace.value
    ? sessions.value.filter((session) => session.workspace_id === deletingWorkspace.value?.id)
        .length
    : 0,
)
const openTerminalSessions = computed(() =>
  terminalRuntimeAvailableSessionIds.value
    .map((sessionId) => sessions.value.find((session) => session.id === sessionId))
    .filter((session): session is Session => !!session),
)
const workspaceLabels = computed(() => workspaceDisplayLabelsById(sessionTree.value))
const createSessionFormKey = computed(() =>
  [
    createSessionContext.value.host || '',
    createSessionContext.value.workspace || '',
    createSessionContext.value.shortcutId || '',
  ].join('\n'),
)

function errorTitle(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback
}

async function refresh() {
  error.value = ''
  sessionRuntimeStateVerified.value = false
  freshTerminalSessionIds.value = []
  const storedLoaded = await loadStoredSessions()
  void environmentStore.ensureLoaded()
  if (!storedLoaded) {
    return
  }

  await refreshLiveSessions()
}

async function loadStoredSessions() {
  initialSessionTreeLoading.value = true
  try {
    applySessionTree((await listSessionTree({ refresh: false })).environments)
    sessionRuntimeStateVerified.value = false
    return true
  } catch (err) {
    const title = errorTitle(err, t('app.errors.loadSessions'))
    if (sessionTree.value.length > 0 || sessions.value.length > 0) {
      toast.show({ title, variant: 'error' })
    } else {
      error.value = title
    }
    return false
  } finally {
    initialSessionTreeLoading.value = false
  }
}

async function loadSessions() {
  await refreshLiveSessions()
}

async function refreshLiveSessions() {
  sessionStatusRefreshing.value = true
  try {
    applySessionTree((await listSessionTree()).environments)
    sessionRuntimeStateVerified.value = true
  } catch (err) {
    const title = errorTitle(err, t('app.errors.loadSessions'))
    if (sessionTree.value.length > 0 || sessions.value.length > 0) {
      toast.show({ title, variant: 'error' })
      return
    }
    error.value = title
  } finally {
    sessionStatusRefreshing.value = false
  }
}

function applySessionTree(tree: SessionEnvironment[]) {
  sessionTree.value = tree
  sessions.value = tree.flatMap((environment) =>
    environment.workspaces.flatMap((workspace) => workspace.entries),
  )
  reconcileOpenTerminalSessions()
}

function reconcileOpenTerminalSessions() {
  const sessionIds = new Set(sessions.value.map((session) => session.id))
  openTerminalSessionIds.value = openTerminalSessionIds.value.filter((sessionId) =>
    sessionIds.has(sessionId),
  )
  freshTerminalSessionIds.value = freshTerminalSessionIds.value.filter((sessionId) =>
    sessionIds.has(sessionId),
  )
  if (activeSessionId.value && !sessionIds.has(activeSessionId.value)) {
    activeSessionId.value = openTerminalSessionIds.value[0]
  }
}

function sessionWorkspaceStatus(entries: Session[]): SessionStatus {
  if (entries.some((entry) => entry.status === 'running')) {
    return 'running'
  }
  if (entries.some((entry) => entry.status === 'disconnected')) {
    return 'disconnected'
  }
  if (entries.some((entry) => entry.status === 'failed')) {
    return 'failed'
  }
  return 'stopped'
}

function isShortcutHost(host: string | null | undefined): host is ShortcutHost {
  return host === 'windows_cygwin' || host === 'windows_wsl' || host === 'linux'
}

function sessionHost(session: Session): ShortcutHost | undefined {
  if (isShortcutHost(session.host)) {
    return session.host
  }
  return isShortcutHost(session.runtime) ? session.runtime : undefined
}

function environmentLabel(host: ShortcutHost) {
  return (
    sessionTree.value.find((environment) => environment.host === host)?.label ||
    environmentStore.environments.find((environment) => environment.host === host)?.label ||
    {
      windows_cygwin: 'Cygwin',
      windows_wsl: 'WSL',
      linux: 'Linux',
    }[host]
  )
}

function workspaceName(path: string) {
  const normalized = path.replace(/\\/g, '/').replace(/\/$/, '')
  return normalized.split('/').filter(Boolean).at(-1) || path
}

function upsertSessionEntry(entries: Session[], session: Session) {
  return entries.some((entry) => entry.id === session.id)
    ? entries.map((entry) => (entry.id === session.id ? session : entry))
    : [...entries, session]
}

function workspaceFromSession(session: Session, host: ShortcutHost): SessionWorkspace {
  return {
    id: session.workspace_id,
    host,
    name: workspaceName(session.workspace),
    path: session.workspace,
    status: sessionWorkspaceStatus([session]),
    entries: [session],
  }
}

function upsertSessionInWorkspace(workspace: SessionWorkspace, session: Session): SessionWorkspace {
  if (workspace.id !== session.workspace_id) {
    return workspace
  }
  const entries = upsertSessionEntry(workspace.entries, session)
  return {
    ...workspace,
    status: sessionWorkspaceStatus(entries),
    entries,
  }
}

function upsertSessionInEnvironment(
  environment: SessionEnvironment,
  session: Session,
  host: ShortcutHost,
): SessionEnvironment {
  if (environment.host !== host) {
    return environment
  }
  const hasWorkspace = environment.workspaces.some((workspace) => workspace.id === session.workspace_id)
  const workspaces = hasWorkspace
    ? environment.workspaces.map((workspace) => upsertSessionInWorkspace(workspace, session))
    : [...environment.workspaces, workspaceFromSession(session, host)]
  return {
    ...environment,
    workspaces,
  }
}

function updateSession(session: Session) {
  sessions.value = upsertSessionEntry(sessions.value, session)
  const host = sessionHost(session)
  if (!host) {
    reconcileOpenTerminalSessions()
    return
  }

  const hasEnvironment = sessionTree.value.some((environment) => environment.host === host)
  const environments = hasEnvironment
    ? sessionTree.value.map((environment) => upsertSessionInEnvironment(environment, session, host))
    : [
        ...sessionTree.value,
        {
          host,
          label: environmentLabel(host),
          workspaces: [workspaceFromSession(session, host)],
        },
      ]
  sessionTree.value = environments
  reconcileOpenTerminalSessions()
}

function removeSessionFromWorkspace(workspace: SessionWorkspace, session: Session): SessionWorkspace {
  if (workspace.id !== session.workspace_id && !workspace.entries.some((entry) => entry.id === session.id)) {
    return workspace
  }
  const entries = workspace.entries.filter((entry) => entry.id !== session.id)
  return {
    ...workspace,
    status: sessionWorkspaceStatus(entries),
    entries,
  }
}

function removeSession(session: Session) {
  sessions.value = sessions.value.filter((entry) => entry.id !== session.id)
  sessionTree.value = sessionTree.value.map((environment) => ({
    ...environment,
    workspaces: environment.workspaces.map((workspace) =>
      removeSessionFromWorkspace(workspace, session),
    ),
  }))
  reconcileOpenTerminalSessions()
}

function openTerminalSession(session: Session, options?: { fresh?: boolean }) {
  if (!sessionRuntimeStateVerified.value && !options?.fresh) {
    return false
  }
  if (options?.fresh && !freshTerminalSessionIds.value.includes(session.id)) {
    freshTerminalSessionIds.value = [...freshTerminalSessionIds.value, session.id]
  }
  if (!openTerminalSessionIds.value.includes(session.id)) {
    openTerminalSessionIds.value = [...openTerminalSessionIds.value, session.id]
  }
  activeSessionId.value = session.id
  return true
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
  if (creatingSession.value) {
    return
  }

  creatingSession.value = true
  try {
    const session = await createSession(payload)
    updateSession(session)
    openTerminalSession(session, { fresh: true })
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
  if (!deletingSession.value || deletingSessionId.value) {
    return
  }

  error.value = ''
  const session = deletingSession.value
  const sessionId = session.id
  deletingSessionId.value = sessionId
  try {
    await deleteSession(sessionId)
    removeSession(session)
    deletingSession.value = undefined
    toast.show({ title: t('app.success.deleteSession'), variant: 'success' })
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.deleteSession')), variant: 'error' })
  } finally {
    deletingSessionId.value = undefined
  }
}

function askRemoveWorkspace(workspace: { id: string; path: string }) {
  deletingWorkspace.value = workspace
}

async function confirmRemoveWorkspace() {
  if (!deletingWorkspace.value || deletingWorkspaceId.value) {
    return
  }

  error.value = ''
  const workspaceId = deletingWorkspace.value.id
  deletingWorkspaceId.value = workspaceId
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
  } finally {
    deletingWorkspaceId.value = undefined
  }
}

async function handleStart(session: Session) {
  if (startingSessionId.value || !sessionRuntimeStateVerified.value) {
    return
  }

  error.value = ''
  startingSessionId.value = session.id
  try {
    const started = await startSession(session.id)
    updateSession(started)
    openTerminalSession(started, { fresh: true })
    toast.show({ title: t('app.success.startSession'), variant: 'success' })
    await router.push('/session')
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.startSession')), variant: 'error' })
  } finally {
    startingSessionId.value = undefined
  }
}

async function handleStop(session: Session) {
  if (stoppingSessionId.value || !sessionRuntimeStateVerified.value) {
    return
  }

  error.value = ''
  stoppingSessionId.value = session.id
  try {
    const stopped = await stopSession(session.id)
    updateSession(stopped)
    openTerminalSession(stopped)
    toast.show({ title: t('app.success.stopSession'), variant: 'success' })
    await router.push('/session')
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.stopSession')), variant: 'error' })
  } finally {
    stoppingSessionId.value = undefined
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
  if (closingAllSessions.value) {
    return
  }

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
  if (!openTerminalSession(session)) {
    return
  }
  showCreatePanel.value = false
  await router.push('/session')
}

async function showCreate(context?: {
  host?: ShortcutHost
  workspace?: string
  shortcutId?: string
}) {
  if (context !== undefined) {
    createSessionContext.value = context
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
          :status-refreshing="sessionStatusRefreshing"
          :runtime-state-verified="sessionRuntimeStateVerified"
          :environments-loading="environmentStore.loading"
          :environments-loaded="environmentStore.loaded"
          :environments-error="environmentStore.error"
          :error="error"
          :compact="compactSidebar"
          :environments="environmentStore.environments"
          :has-ready-environment="environmentStore.hasReadyEnvironment"
          :starting-session-id="startingSessionId"
          :stopping-session-id="stoppingSessionId"
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
        <RouterView v-slot="{ Component, route }">
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
                  :key="createSessionFormKey"
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
            <section
              v-else-if="
                route.path === '/session' &&
                !sessionRuntimeStateVerified &&
                sessions.length > 0 &&
                openTerminalSessions.length === 0
              "
              key="runtime-unverified"
              class="flex h-full min-h-0 items-center justify-center bg-slate-100 text-slate-600 dark:bg-slate-950 dark:text-slate-300"
            >
              <div class="grid justify-items-center gap-3 text-sm">
                <Loader2 class="h-10 w-10 animate-spin text-slate-400 dark:text-slate-500" />
                <span>{{ t('session.terminal.refreshingStatus') }}</span>
              </div>
            </section>
            <component
              :is="Component"
              v-else
              :sessions="openTerminalSessions"
              :session="terminalActiveSession"
              :starting-session-id="startingSessionId"
              :workspace-labels="workspaceLabels"
              @close="closeTerminalSession"
              @create="showCreate({})"
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

    <div
      v-if="initialSessionTreeLoading"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-slate-100/90 backdrop-blur-sm dark:bg-slate-950/90"
    >
      <div
        class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 text-slate-700 shadow-xl shadow-blue-900/10 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:shadow-none"
      >
        <Loader2 class="h-5 w-5 animate-spin text-blue-600 dark:text-blue-400" />
        <span class="font-medium">{{ t('app.loading.restoreSessions') }}</span>
      </div>
    </div>

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
              :disabled="!!deletingSessionId"
              class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <button
              type="button"
              :disabled="!!deletingSessionId"
              class="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-white disabled:cursor-wait disabled:opacity-60"
              @click="confirmRemove"
            >
              <Loader2 v-if="deletingSessionId" class="h-4 w-4 animate-spin" />
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
              :disabled="!!deletingWorkspaceId"
              class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <button
              type="button"
              :disabled="!!deletingWorkspaceId"
              class="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-white disabled:cursor-wait disabled:opacity-60"
              :class="
                deletingWorkspaceSessionCount > 0
                  ? 'bg-amber-600 hover:bg-amber-700'
                  : 'bg-slate-900 hover:bg-slate-800 dark:bg-slate-700 dark:hover:bg-slate-600'
              "
              @click="confirmRemoveWorkspace"
            >
              <Loader2 v-if="deletingWorkspaceId" class="h-4 w-4 animate-spin" />
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
              :disabled="closingAllSessions"
              class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <button
              type="button"
              :disabled="closingAllSessions"
              class="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-white disabled:cursor-wait disabled:opacity-60"
              @click="confirmCloseAllSessions"
            >
              <Loader2 v-if="closingAllSessions" class="h-4 w-4 animate-spin" />
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
