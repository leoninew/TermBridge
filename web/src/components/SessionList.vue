<script setup lang="ts">
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  Folder,
  Languages,
  LaptopMinimal,
  PanelLeftClose,
  Loader2,
  RefreshCw,
  Moon,
  Plus,
  Search,
  Settings,
  Ban,
  Sun,
  SquareTerminal,
  Trash2,
  Unplug,
  XCircle,
} from '@lucide/vue'
import { VueDraggable } from 'vue-draggable-plus'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuRoot,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from 'reka-ui'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import CygwinLogo from './CygwinLogo.vue'
import LinuxLogo from './LinuxLogo.vue'
import WslLogo from './WslLogo.vue'
import { workspaceDisplayLabels } from '../sessionTreeLabels'
import { useThemeStore } from '../stores/theme'
import type {
  EnvironmentSummary,
  Session,
  SessionEnvironment,
  SessionWorkspace,
  ShortcutHost,
} from '../types/sessions'

type SessionTreeNode = {
  id: string
  label: string
  kind: 'workspace' | 'session'
  host: ShortcutHost
  workspaceId?: string
  workspacePath?: string
  children?: SessionTreeNode[]
  session?: Session
}

type SessionTreeGroup = {
  id: string
  label: string
  host: ShortcutHost
  nodes: SessionTreeNode[]
}

type DragEndEvent = {
  oldIndex?: number
  newIndex?: number
  from: globalThis.HTMLElement
  to: globalThis.HTMLElement
  item: globalThis.HTMLElement
}

const { locale, t } = useI18n()
const theme = useThemeStore()
const query = ref('')
const selectedTreeNodes = ref<SessionTreeNode[]>([])
const expandedTreeKeys = ref<string[]>([])
const displayTreeGroups = ref<SessionTreeGroup[]>([])
const lastDefaultExpansionKey = ref('')

const props = defineProps<{
  sessions: Session[]
  sessionTree: SessionEnvironment[]
  activeSessionId?: string
  loading: boolean
  environmentsLoading: boolean
  error: string
  compact?: boolean
  environments: EnvironmentSummary[]
  hasReadyEnvironment: boolean
  startingSessionId?: string
  stoppingSessionId?: string
}>()

const emit = defineEmits<{
  create: []
  collapse: []
  createContext: [context: { host?: ShortcutHost; workspace?: string }]
  select: [session: Session]
  start: [session: Session]
  stop: [session: Session]
  remove: [session: Session]
  removeWorkspace: [workspace: { id: string; path: string }]
  reorderWorkspaces: [payload: { host: ShortcutHost; workspaceIds: string[] }]
  reorderSessions: [payload: { workspaceId: string; sessionIds: string[] }]
  closeAll: []
  navigate: [path: string]
}>()

const filteredTree = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) {
    return props.sessionTree
  }
  return props.sessionTree
    .map((environment) => {
      const workspaces = environment.workspaces.filter((workspace) =>
        workspace.path.toLowerCase().includes(needle),
      )
      return workspaces.length > 0 ? { ...environment, workspaces } : undefined
    })
    .filter((environment): environment is SessionEnvironment => !!environment)
})

const treeGroups = computed<SessionTreeGroup[]>(() =>
  filteredTree.value.map((environment) => ({
    id: `environment:${environment.host}`,
    label: environment.label,
    host: environment.host,
    nodes: workspaceNodes(environment.workspaces),
  })),
)

const hasWorkspaceNodes = computed(() =>
  props.sessionTree.some((environment) => environment.workspaces.length > 0),
)
const shouldShowEmptySessions = computed(
  () => props.sessions.length === 0 && !hasWorkspaceNodes.value,
)

watch(
  [treeGroups, () => props.activeSessionId, query],
  ([groups, activeSessionId]) => {
    const nextGroups = groups.map((group) => ({
      ...group,
      nodes: group.nodes.map((node) => ({
        ...node,
        children: node.children ? [...node.children] : [],
      })),
    }))
    const nextNodes = nextGroups.flatMap((group) => group.nodes)
    const allWorkspaceKeys = collectExpandableKeys(nextNodes)
    const defaultExpandedKeys = query.value ? allWorkspaceKeys : activeWorkspaceKeys(nextNodes)
    const activeWorkspaceKey = defaultExpandedKeys.join('|')
    const defaultExpansionKey = [query.value, activeWorkspaceKey, allWorkspaceKeys.join('|')].join(
      '\n',
    )

    displayTreeGroups.value = nextGroups
    selectedTreeNodes.value = asSelectedList(
      activeSessionId ? findTreeNode(nextNodes, `session:${activeSessionId}`) : undefined,
    )

    if (query.value) {
      expandedTreeKeys.value = defaultExpandedKeys
      lastDefaultExpansionKey.value = defaultExpansionKey
      return
    }

    const nextExpandedKeys = new Set(
      expandedTreeKeys.value.filter((key) => allWorkspaceKeys.includes(key)),
    )
    if (defaultExpansionKey !== lastDefaultExpansionKey.value) {
      defaultExpandedKeys.forEach((key) => nextExpandedKeys.add(key))
      lastDefaultExpansionKey.value = defaultExpansionKey
    }
    expandedTreeKeys.value = [...nextExpandedKeys]
  },
  { immediate: true },
)

function workspaceNodes(workspaces: SessionWorkspace[]): SessionTreeNode[] {
  const workspaceLabels = workspaceDisplayLabels(workspaces)
  return workspaces.map((workspace) => ({
    id: `workspace:${workspace.id}`,
    kind: 'workspace',
    label: workspaceLabels.get(workspace.id) || workspace.path,
    host: workspace.host,
    workspaceId: workspace.id,
    workspacePath: workspace.path,
    children: workspace.entries.map((session) => ({
      id: `session:${session.id}`,
      kind: 'session',
      label: session.name,
      host: workspace.host,
      workspacePath: workspace.path,
      session,
    })),
  }))
}

function collectExpandableKeys(nodes: SessionTreeNode[]): string[] {
  return nodes.flatMap((node) => [
    ...(node.children?.length ? [node.id] : []),
    ...collectExpandableKeys(node.children || []),
  ])
}

function isActiveStatus(session: Session): boolean {
  return (
    session.status === 'running' ||
    session.status === 'starting' ||
    session.status === 'disconnected'
  )
}

function activeWorkspaceKeys(nodes: SessionTreeNode[]): string[] {
  return nodes.flatMap((node) =>
    node.children?.some((child) => child.session && isActiveStatus(child.session)) ? [node.id] : [],
  )
}

function findTreeNode(nodes: SessionTreeNode[], id: string): SessionTreeNode | undefined {
  for (const node of nodes) {
    if (node.id === id) {
      return node
    }
    const child = findTreeNode(node.children || [], id)
    if (child) {
      return child
    }
  }
  return undefined
}

function asSelectedList(node: SessionTreeNode | undefined): SessionTreeNode[] {
  return node ? [node] : []
}

function isSelectedNode(node: SessionTreeNode): boolean {
  return selectedTreeNodes.value.some((selected) => selected.id === node.id)
}

function isExpandedNode(node: SessionTreeNode): boolean {
  return expandedTreeKeys.value.includes(node.id)
}

function groupWorkspaceKeys(group: SessionTreeGroup): string[] {
  return collectExpandableKeys(group.nodes)
}

function isExpandedGroup(group: SessionTreeGroup): boolean {
  const workspaceKeys = groupWorkspaceKeys(group)
  return (
    workspaceKeys.length > 0 && workspaceKeys.every((key) => expandedTreeKeys.value.includes(key))
  )
}

function hasVisibleGroupNodes(group: SessionTreeGroup): boolean {
  return group.nodes.length > 0
}

function toggleGroupExpanded(event: globalThis.MouseEvent, group: SessionTreeGroup) {
  event.preventDefault()
  event.stopPropagation()

  const workspaceKeys = groupWorkspaceKeys(group)
  if (isExpandedGroup(group)) {
    expandedTreeKeys.value = expandedTreeKeys.value.filter((key) => !workspaceKeys.includes(key))
    return
  }

  const nextTreeKeys = new Set(expandedTreeKeys.value)
  workspaceKeys.forEach((key) => nextTreeKeys.add(key))
  expandedTreeKeys.value = [...nextTreeKeys]
}

function toggleExpanded(event: globalThis.MouseEvent, node: SessionTreeNode) {
  event.preventDefault()
  event.stopPropagation()
  if (!node.children?.length) {
    return
  }
  expandedTreeKeys.value = isExpandedNode(node)
    ? expandedTreeKeys.value.filter((key) => key !== node.id)
    : [...expandedTreeKeys.value, node.id]
}

function hasDragged(event: DragEndEvent) {
  return (
    event.oldIndex !== undefined &&
    event.newIndex !== undefined &&
    event.oldIndex !== event.newIndex
  )
}

function mergeVisibleOrder(fullIds: string[], visibleIds: string[]): string[] {
  const visibleIdSet = new Set(visibleIds)
  const orderedVisibleIds = [...visibleIds]
  return fullIds.map((id) => (visibleIdSet.has(id) ? orderedVisibleIds.shift() || id : id))
}

function sameOrder(left: string[], right: string[]) {
  return left.length === right.length && left.every((id, index) => id === right[index])
}

function handleWorkspaceReorder(event: DragEndEvent, host: ShortcutHost, nodes: SessionTreeNode[]) {
  if (!hasDragged(event)) {
    return
  }

  const environment = props.sessionTree.find((item) => item.host === host)
  if (!environment) {
    return
  }

  const fullWorkspaceIds = environment.workspaces.map((workspace) => workspace.id)
  const visibleWorkspaceIds = nodes
    .map((node) => node.workspaceId)
    .filter((id): id is string => !!id)
  const workspaceIds = mergeVisibleOrder(fullWorkspaceIds, visibleWorkspaceIds)
  if (
    workspaceIds.length !== fullWorkspaceIds.length ||
    sameOrder(workspaceIds, fullWorkspaceIds)
  ) {
    return
  }

  emit('reorderWorkspaces', { host, workspaceIds })
}

function handleSessionReorder(
  event: DragEndEvent,
  workspace: SessionTreeNode,
  nodes: SessionTreeNode[],
) {
  if (!workspace.workspaceId || !hasDragged(event)) {
    return
  }

  const sourceWorkspace = props.sessionTree
    .flatMap((environment) => environment.workspaces)
    .find((item) => item.id === workspace.workspaceId)
  if (!sourceWorkspace) {
    return
  }

  const fullSessionIds = sourceWorkspace.entries.map((session) => session.id)
  const visibleSessionIds = nodes.map((node) => node.session?.id).filter((id): id is string => !!id)
  const sessionIds = mergeVisibleOrder(fullSessionIds, visibleSessionIds)
  if (sessionIds.length !== fullSessionIds.length || sameOrder(sessionIds, fullSessionIds)) {
    return
  }

  emit('reorderSessions', { workspaceId: workspace.workspaceId, sessionIds })
}

function isStartingSession(session: Session): boolean {
  return props.startingSessionId === session.id
}

function isStoppingSession(session: Session): boolean {
  return props.stoppingSessionId === session.id
}

function startSessionLabel(session: Session): string {
  return t(
    session.status === 'disconnected' ? 'session.card.reconnectLabel' : 'session.card.startLabel',
  )
}

function sessionStatusTextClass(session: Session): string {
  if (session.status === 'running') {
    return 'text-emerald-700 dark:text-emerald-300'
  }
  if (session.status === 'failed') {
    return 'text-red-700 dark:text-red-300'
  }
  if (session.status === 'starting') {
    return 'text-blue-700 dark:text-blue-300'
  }
  if (session.status === 'disconnected') {
    return 'text-amber-700 dark:text-amber-300'
  }
  return 'text-slate-600 dark:text-slate-300'
}

function sessionStatusIconClass(session: Session): string {
  if (session.status === 'running') {
    return 'text-emerald-600 dark:text-emerald-400'
  }
  if (session.status === 'failed') {
    return 'text-red-600 dark:text-red-400'
  }
  if (session.status === 'starting') {
    return 'text-blue-600 dark:text-blue-400'
  }
  if (session.status === 'disconnected') {
    return 'text-amber-600 dark:text-amber-300'
  }
  return 'text-slate-400 dark:text-slate-400'
}

function sessionStatusIcon(session: Session) {
  if (session.status === 'disconnected') {
    return Unplug
  }
  return SquareTerminal
}

function environmentLogo(host: ShortcutHost) {
  if (host === 'windows_cygwin') {
    return CygwinLogo
  }
  if (host === 'windows_wsl') {
    return WslLogo
  }
  return LinuxLogo
}

function handleCreate() {
  const node = selectedTreeNodes.value[0]
  emit('createContext', node ? { host: node.host, workspace: node.workspacePath } : {})
  emit('create')
}

function handleTreeSelect(node: SessionTreeNode) {
  selectedTreeNodes.value = [node]
  if (node.session) {
    emit('select', node.session)
  }
}

function startSession(event: globalThis.MouseEvent, session: Session) {
  event.preventDefault()
  event.stopPropagation()
  emit('start', session)
}

function stopSession(event: globalThis.MouseEvent, session: Session) {
  event.preventDefault()
  event.stopPropagation()
  emit('stop', session)
}

function removeSession(event: globalThis.MouseEvent, session: Session) {
  event.preventDefault()
  event.stopPropagation()
  emit('remove', session)
}

function createFromWorkspace(event: globalThis.MouseEvent, node: SessionTreeNode) {
  event.preventDefault()
  event.stopPropagation()
  emit('createContext', { host: node.host, workspace: node.workspacePath })
  emit('create')
}

function removeWorkspace(event: globalThis.MouseEvent, node: SessionTreeNode) {
  event.preventDefault()
  event.stopPropagation()
  if (node.workspaceId && node.workspacePath) {
    emit('removeWorkspace', { id: node.workspaceId, path: node.workspacePath })
  }
}
</script>

<template>
  <section
    class="flex h-full min-h-0 flex-col overflow-hidden border-r border-slate-200/70 bg-slate-100 text-slate-700 opacity-90 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 lg:border-r-0"
  >
    <div class="flex min-h-0 flex-1 flex-col gap-2.5 px-2 pb-0">
      <p
        v-if="loading || environmentsLoading"
        class="inline-flex items-center gap-2 text-sm text-slate-500"
      >
        <Loader2 class="h-4 w-4 animate-spin" />
        {{ t('session.list.loading') }}
      </p>
      <p v-else-if="error" class="inline-flex items-center gap-2 text-sm text-red-600">
        <AlertCircle class="h-4 w-4" />
        {{ error }}
      </p>
      <div
        v-else-if="sessions.length === 0 && !hasReadyEnvironment"
        class="grid gap-3 border-l border-amber-300 bg-amber-50/70 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200"
      >
        <p>{{ t('session.list.noReadyEnvironment') }}</p>
        <button
          type="button"
          class="justify-self-start rounded-lg bg-amber-600 px-3 py-2 text-white transition hover:bg-amber-700"
          @click="emit('navigate', '/environment')"
        >
          {{ t('session.list.goToEnvironment') }}
        </button>
      </div>
      <p v-else-if="shouldShowEmptySessions" class="text-sm text-slate-500">
        {{ t('session.list.emptyPrefix') }}
        <button
          type="button"
          class="text-blue-600 transition hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-200"
          @click="handleCreate"
        >
          {{ t('session.list.emptyCreateLink') }}
        </button>
        {{ t('session.list.emptySuffix') }}
      </p>
      <div v-else class="flex min-h-0 flex-1 flex-col">
        <div
          class="-mx-2 flex h-11 items-center gap-2 border-b border-slate-200/70 px-2 dark:border-slate-800"
        >
          <label class="relative min-w-0 flex-1">
            <Search
              class="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400 dark:text-slate-400"
            />
            <input
              v-model.trim="query"
              class="h-8 w-full rounded-md border border-slate-300/70 bg-white/45 py-1 pl-8 pr-3 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:bg-white/65 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-400 dark:focus:border-blue-500 dark:focus:bg-slate-900"
              :placeholder="t('session.list.searchPlaceholder')"
            />
          </label>
          <button
            type="button"
            :disabled="!hasReadyEnvironment"
            class="inline-flex h-8 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-slate-300/70 bg-white/35 px-2.5 text-sm font-medium text-slate-600 transition hover:border-blue-300 hover:bg-blue-50/70 hover:text-blue-700 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-blue-500/70 dark:hover:bg-blue-950/70 dark:hover:text-blue-200"
            @click="handleCreate"
          >
            <Plus class="h-4 w-4" />
            {{ t('session.terminal.createTab') }}
          </button>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-1 pt-2">
          <div class="grid min-w-0 gap-3">
            <section v-for="group in displayTreeGroups" :key="group.id" class="grid min-w-0 gap-1">
              <div
                class="flex min-w-0 items-center gap-2 px-1.5 py-1 text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-400"
              >
                <component :is="environmentLogo(group.host)" class="shrink-0" />
                <span class="min-w-0 flex-1 truncate">{{ group.label }}</span>
                <button
                  type="button"
                  class="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-400 transition hover:bg-white/45 hover:text-slate-700 focus:outline-none disabled:cursor-default disabled:opacity-40 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  :disabled="!hasVisibleGroupNodes(group)"
                  :aria-label="
                    isExpandedGroup(group)
                      ? t('session.list.collapseGroup')
                      : t('session.list.expandGroup')
                  "
                  :title="
                    isExpandedGroup(group)
                      ? t('session.list.collapseGroup')
                      : t('session.list.expandGroup')
                  "
                  @click="toggleGroupExpanded($event, group)"
                >
                  <ChevronsDownUp v-if="isExpandedGroup(group)" class="h-4 w-4" />
                  <ChevronsUpDown v-else class="h-4 w-4" />
                </button>
              </div>
              <VueDraggable
                v-if="hasVisibleGroupNodes(group)"
                v-model="group.nodes"
                :group="{ name: `workspaces:${group.host}`, pull: false, put: false }"
                ghost-class="session-list-ghost"
                filter="button"
                :prevent-on-filter="false"
                class="grid min-w-0 gap-px outline-none"
                @end="handleWorkspaceReorder($event, group.host, group.nodes)"
              >
                <div
                  v-for="workspace in group.nodes"
                  :key="workspace.id"
                  class="grid min-w-0 gap-px"
                >
                  <div
                    class="group flex w-full min-w-0 items-center gap-1.5 rounded-md py-1 pr-1.5 text-left text-[13px] leading-5 transition focus:outline-none"
                    :class="
                      isSelectedNode(workspace)
                        ? 'bg-blue-100/65 text-blue-800 ring-1 ring-inset ring-blue-200/70 dark:bg-blue-950/70 dark:text-blue-100 dark:ring-blue-700/60'
                        : 'text-slate-600 hover:bg-white/45 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-50'
                    "
                  >
                    <button
                      type="button"
                      class="inline-flex h-4 w-4 shrink-0 items-center justify-center text-slate-400 dark:text-slate-400"
                      @click="toggleExpanded($event, workspace)"
                    >
                      <ChevronDown
                        v-if="workspace.children?.length && isExpandedNode(workspace)"
                        class="h-4 w-4"
                      />
                      <ChevronRight v-else-if="workspace.children?.length" class="h-4 w-4" />
                    </button>
                    <Folder class="h-4 w-4 shrink-0 text-slate-400 dark:text-slate-400" />
                    <span
                      class="min-w-0 flex-1 truncate"
                      :title="workspace.workspacePath"
                      @click="handleTreeSelect(workspace)"
                    >
                      {{ workspace.label }}
                    </span>
                    <span
                      class="ml-auto inline-flex shrink-0 items-center gap-1 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100"
                    >
                      <button
                        type="button"
                        class="inline-flex h-5 w-5 items-center justify-center rounded text-slate-400/70 transition hover:bg-blue-100/60 hover:text-blue-700 focus:opacity-100 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-blue-300"
                        :aria-label="t('session.workspace.createLabel')"
                        :title="t('session.workspace.createLabel')"
                        @click="createFromWorkspace($event, workspace)"
                      >
                        <Plus class="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        class="inline-flex h-5 w-5 items-center justify-center rounded text-slate-400/70 transition hover:bg-red-100/60 hover:text-red-600 focus:opacity-100 dark:text-slate-400 dark:hover:bg-red-950/70 dark:hover:text-red-300"
                        :aria-label="t('session.workspace.deleteLabel')"
                        :title="t('session.workspace.deleteLabel')"
                        @click="removeWorkspace($event, workspace)"
                      >
                        <Trash2 class="h-4 w-4" />
                      </button>
                    </span>
                  </div>
                  <VueDraggable
                    v-if="workspace.children?.length && isExpandedNode(workspace)"
                    v-model="workspace.children"
                    :group="{ name: `sessions:${workspace.workspaceId}`, pull: false, put: false }"
                    ghost-class="session-list-ghost"
                    filter="button"
                    :prevent-on-filter="false"
                    class="ml-7 grid min-w-0 gap-px border-l border-slate-200/70 pl-3 dark:border-slate-800"
                    @end="handleSessionReorder($event, workspace, workspace.children || [])"
                  >
                    <div
                      v-for="sessionNode in workspace.children"
                      :key="sessionNode.id"
                      class="group flex w-full min-w-0 items-center gap-1.5 rounded-md py-1 pr-1.5 text-left text-[13px] leading-5 transition focus:outline-none"
                      :class="
                        isSelectedNode(sessionNode)
                          ? 'bg-blue-100/65 text-blue-800 ring-1 ring-inset ring-blue-200/70 dark:bg-blue-950/70 dark:text-blue-100 dark:ring-blue-700/60'
                          : 'text-slate-600 hover:bg-white/45 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-50'
                      "
                    >
                      <component
                        :is="
                          sessionNode.session
                            ? sessionStatusIcon(sessionNode.session)
                            : SquareTerminal
                        "
                        class="h-4 w-4 shrink-0"
                        :class="
                          sessionNode.session
                            ? sessionStatusIconClass(sessionNode.session)
                            : 'text-slate-400 dark:text-slate-400'
                        "
                      />
                      <span
                        class="min-w-0 flex-1 truncate"
                        :class="
                          sessionNode.session ? sessionStatusTextClass(sessionNode.session) : ''
                        "
                        @click="handleTreeSelect(sessionNode)"
                      >
                        {{ sessionNode.label }}
                      </span>
                      <span
                        v-if="sessionNode.session"
                        class="inline-flex shrink-0 items-center gap-1"
                      >
                        <button
                          v-if="sessionNode.session.status === 'running'"
                          type="button"
                          :disabled="isStoppingSession(sessionNode.session)"
                          class="relative inline-flex h-5 w-5 items-center justify-center rounded text-slate-400 transition hover:bg-amber-100/60 hover:text-amber-600 disabled:cursor-wait disabled:opacity-60 dark:text-slate-400 dark:hover:bg-amber-950/70 dark:hover:text-amber-300"
                          :aria-label="t('session.card.stopLabel')"
                          :title="t('session.card.stopLabel')"
                          @click="stopSession($event, sessionNode.session)"
                        >
                          <Loader2
                            v-if="isStoppingSession(sessionNode.session)"
                            class="h-4 w-4 animate-spin"
                          />
                          <Ban v-else class="h-4 w-4" />
                        </button>
                        <span
                          v-if="
                            sessionNode.session.status === 'disconnected' &&
                            isStartingSession(sessionNode.session)
                          "
                          class="inline-flex h-5 w-5 items-center justify-center rounded text-slate-400 dark:text-slate-400"
                          :aria-label="startSessionLabel(sessionNode.session)"
                          :title="startSessionLabel(sessionNode.session)"
                        >
                          <Loader2 class="h-4 w-4 animate-spin" />
                        </span>
                        <button
                          v-if="
                            sessionNode.session.status === 'disconnected' &&
                            !isStartingSession(sessionNode.session)
                          "
                          type="button"
                          class="inline-flex h-5 w-5 items-center justify-center rounded text-slate-400 transition hover:bg-blue-100/60 hover:text-blue-600 dark:text-slate-400 dark:hover:bg-blue-950/70 dark:hover:text-blue-300"
                          :aria-label="startSessionLabel(sessionNode.session)"
                          :title="startSessionLabel(sessionNode.session)"
                          @click="startSession($event, sessionNode.session)"
                        >
                          <RefreshCw class="h-4 w-4" />
                        </button>
                        <button
                          v-if="sessionNode.session.status === 'disconnected'"
                          type="button"
                          :disabled="isStoppingSession(sessionNode.session)"
                          class="relative inline-flex h-5 w-5 items-center justify-center rounded text-slate-400 transition hover:bg-amber-100/60 hover:text-amber-600 disabled:cursor-wait disabled:opacity-60 dark:text-slate-400 dark:hover:bg-amber-950/70 dark:hover:text-amber-300"
                          :aria-label="t('session.card.stopLabel')"
                          :title="t('session.card.stopLabel')"
                          @click="stopSession($event, sessionNode.session)"
                        >
                          <Loader2
                            v-if="isStoppingSession(sessionNode.session)"
                            class="h-4 w-4 animate-spin"
                          />
                          <Ban v-else class="h-4 w-4" />
                        </button>
                        <button
                          v-if="sessionNode.session.status === 'stopped'"
                          type="button"
                          class="inline-flex h-5 w-5 items-center justify-center rounded text-slate-400 transition hover:bg-red-100/60 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-950/70 dark:hover:text-red-300"
                          :aria-label="t('session.card.deleteLabel')"
                          :title="t('session.card.deleteLabel')"
                          @click="removeSession($event, sessionNode.session)"
                        >
                          <Trash2 class="h-4 w-4" />
                        </button>
                      </span>
                    </div>
                  </VueDraggable>
                </div>
              </VueDraggable>
            </section>
          </div>
        </div>
      </div>
    </div>

    <div
      class="mt-auto flex h-7 items-center gap-2 border-t border-slate-200/70 bg-slate-100/80 px-2.5 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-950"
    >
      <DropdownMenuRoot>
        <DropdownMenuTrigger
          class="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-500 transition hover:bg-white/50 hover:text-slate-800 focus:outline-none dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
          :aria-label="t('app.settings.trigger')"
          :title="t('app.settings.trigger')"
        >
          <Settings class="h-4 w-4" />
        </DropdownMenuTrigger>
        <DropdownMenuPortal>
          <DropdownMenuContent
            :side-offset="8"
            align="start"
            side="top"
            class="z-50 min-w-56 rounded-lg border border-slate-200 bg-white p-1 text-sm text-slate-700 shadow-lg shadow-blue-900/5 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:shadow-none"
          >
            <DropdownMenuLabel class="px-3 py-2 text-sm uppercase tracking-wide text-slate-400">
              {{ t('app.settings.navigation') }}
            </DropdownMenuLabel>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
              @select="emit('navigate', '/environment')"
            >
              <span class="inline-flex items-center gap-2">
                <LaptopMinimal class="h-4 w-4 text-slate-500 dark:text-slate-400" />
                {{ t('app.nav.environment') }}
              </span>
              <ChevronRight class="h-4 w-4 text-slate-400" />
            </DropdownMenuItem>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
              @select="emit('navigate', '/shortcuts')"
            >
              <span class="inline-flex items-center gap-2">
                <SquareTerminal class="h-4 w-4 text-slate-500" />
                {{ t('app.nav.shortcuts') }}
              </span>
              <ChevronRight class="h-4 w-4 text-slate-400" />
            </DropdownMenuItem>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-amber-700 outline-none hover:bg-amber-50 focus:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-950/70 dark:focus:bg-amber-950/40"
              @select="emit('closeAll')"
            >
              <span class="inline-flex items-center gap-2">
                <XCircle class="h-4 w-4" />
                {{ t('app.settings.closeAllSessions') }}
              </span>
            </DropdownMenuItem>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger
                class="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
              >
                <span class="inline-flex items-center gap-2">
                  <Sun class="h-4 w-4 text-slate-500 dark:text-slate-400" />
                  {{ t('app.theme.label') }}
                </span>
                <ChevronRight class="h-4 w-4 text-slate-400" />
              </DropdownMenuSubTrigger>
              <DropdownMenuPortal>
                <DropdownMenuSubContent
                  :side-offset="8"
                  class="z-50 min-w-40 rounded-lg border border-slate-200 bg-white p-1 text-sm text-slate-700 shadow-lg shadow-blue-900/5 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:shadow-none"
                >
                  <DropdownMenuRadioGroup v-model="theme.mode">
                    <DropdownMenuRadioItem
                      value="light"
                      class="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
                    >
                      <Check
                        :class="theme.mode === 'light' ? 'opacity-100' : 'opacity-0'"
                        class="h-4 w-4 text-blue-600"
                      />
                      <Sun class="h-4 w-4 text-slate-500 dark:text-slate-400" />
                      {{ t('app.theme.light') }}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem
                      value="dark"
                      class="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
                    >
                      <Check
                        :class="theme.mode === 'dark' ? 'opacity-100' : 'opacity-0'"
                        class="h-4 w-4 text-blue-600"
                      />
                      <Moon class="h-4 w-4 text-slate-500 dark:text-slate-400" />
                      {{ t('app.theme.dark') }}
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuPortal>
            </DropdownMenuSub>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger
                class="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
              >
                <span class="inline-flex items-center gap-2">
                  <Languages class="h-4 w-4 text-slate-500 dark:text-slate-400" />
                  {{ t('app.language.label') }}
                </span>
                <ChevronRight class="h-4 w-4 text-slate-400" />
              </DropdownMenuSubTrigger>
              <DropdownMenuPortal>
                <DropdownMenuSubContent
                  :side-offset="8"
                  class="z-50 min-w-40 rounded-lg border border-slate-200 bg-white p-1 text-sm text-slate-700 shadow-lg shadow-blue-900/5 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:shadow-none"
                >
                  <DropdownMenuRadioGroup v-model="locale">
                    <DropdownMenuRadioItem
                      value="zh-CN"
                      class="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
                    >
                      <Check
                        :class="locale === 'zh-CN' ? 'opacity-100' : 'opacity-0'"
                        class="h-4 w-4 text-blue-600"
                      />
                      {{ t('app.language.zhCN') }}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem
                      value="en-US"
                      class="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
                    >
                      <Check
                        :class="locale === 'en-US' ? 'opacity-100' : 'opacity-0'"
                        class="h-4 w-4 text-blue-600"
                      />
                      {{ t('app.language.enUS') }}
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuPortal>
            </DropdownMenuSub>
          </DropdownMenuContent>
        </DropdownMenuPortal>
      </DropdownMenuRoot>
      <button
        type="button"
        class="ml-auto inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-500 transition hover:bg-slate-900 hover:text-slate-200"
        :aria-label="t('session.list.collapse')"
        :title="t('session.list.collapse')"
        @click="emit('collapse')"
      >
        <PanelLeftClose class="h-4 w-4" />
      </button>
    </div>
  </section>
</template>

<style scoped>
:deep(.session-list-ghost) {
  border-radius: 0.375rem;
  background-color: rgb(219 234 254 / 0.7);
}

:global(.dark) :deep(.session-list-ghost) {
  background-color: rgb(23 37 84 / 0.5);
}
</style>
