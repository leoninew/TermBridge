<script setup lang="ts">
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  Folder,
  Languages,
  LaptopMinimal,
  PanelLeftClose,
  Loader2,
  Moon,
  Plus,
  Search,
  Settings,
  Ban,
  Sun,
  SquareTerminal,
  Trash2,
  XCircle,
} from '@lucide/vue'
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
  TreeItem,
  TreeRoot,
} from 'reka-ui'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import CygwinLogo from './CygwinLogo.vue'
import LinuxLogo from './LinuxLogo.vue'
import WslLogo from './WslLogo.vue'
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
  kind: 'environment' | 'workspace' | 'session'
  host: ShortcutHost
  workspaceId?: string
  workspacePath?: string
  children?: SessionTreeNode[]
  session?: Session
}

const { locale, t } = useI18n()
const theme = useThemeStore()
const query = ref('')
const selectedTreeNodes = ref<SessionTreeNode[]>([])
const expandedTreeKeys = ref<string[]>([])

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
      const environmentMatches = matches(environment.label, environment.host, needle)
      const workspaces = environment.workspaces
        .map((workspace) => {
          const workspaceMatches = matches(workspace.name, workspace.path, needle)
          const entries = workspace.entries.filter(
            (entry) =>
              workspaceMatches ||
              environmentMatches ||
              matches(entry.name, entry.shortcut_name || '', entry.runtime, needle),
          )
          return entries.length > 0 || workspaceMatches ? { ...workspace, entries } : undefined
        })
        .filter((workspace): workspace is SessionWorkspace => !!workspace)
      return workspaces.length > 0 || environmentMatches
        ? { ...environment, workspaces }
        : undefined
    })
    .filter((environment): environment is SessionEnvironment => !!environment)
})

const treeNodes = computed<SessionTreeNode[]>(() =>
  filteredTree.value.map((environment) => ({
    id: `environment:${environment.host}`,
    kind: 'environment',
    label: environment.label,
    host: environment.host,
    children: environment.workspaces.map((workspace) => ({
      id: `workspace:${workspace.id}`,
      kind: 'workspace',
      label: workspace.path,
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
    })),
  })),
)

const hasWorkspaceNodes = computed(() => props.sessionTree.some((environment) => environment.workspaces.length > 0))
const shouldShowEmptySessions = computed(() => props.sessions.length === 0 && !hasWorkspaceNodes.value)

const defaultExpandedTreeKeys = computed(() => collectExpandableKeys(treeNodes.value))
const selectedSession = computed(() => selectedTreeNodes.value[0]?.session)
const selectedShortcutLabel = computed(() => selectedSession.value?.shortcut_name || selectedSession.value?.runtime || '')

watch(
  defaultExpandedTreeKeys,
  (keys) => {
    expandedTreeKeys.value = keys
  },
  { immediate: true },
)

watch(
  [treeNodes, () => props.activeSessionId],
  ([nodes, activeSessionId]) => {
    const selectedNode = activeSessionId ? findTreeNode(nodes, `session:${activeSessionId}`) : undefined
    selectedTreeNodes.value = asSelectedList(selectedNode)
  },
  { immediate: true },
)

function matches(...values: string[]) {
  const needle = values.pop() || ''
  return values.some((value) => value.toLowerCase().includes(needle))
}

function collectExpandableKeys(nodes: SessionTreeNode[]): string[] {
  return nodes.flatMap((node) => [
    ...(node.children?.length ? [node.id] : []),
    ...collectExpandableKeys(node.children || []),
  ])
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

function isStartingSession(session: Session): boolean {
  return props.startingSessionId === session.id
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
  emit('createContext', { host: node.host, workspace: node.workspacePath })
  if (node.session) {
    emit('select', node.session)
  }
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
    class="flex h-full min-h-0 flex-col overflow-hidden border-r border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950"
  >
    <div class="flex items-center justify-between gap-3 px-4 pb-2 pt-4">
      <div class="flex min-w-0 items-center gap-2">
        <button
          type="button"
          class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          :aria-label="t('session.list.collapse')"
          :title="t('session.list.collapse')"
          @click="emit('collapse')"
        >
          <PanelLeftClose class="h-4 w-4" />
        </button>
        <h2 class="truncate text-lg font-semibold text-slate-950 dark:text-slate-100">{{ t('session.list.title') }}</h2>
      </div>
      <button
        type="button"
        :disabled="!hasReadyEnvironment"
        class="inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg bg-blue-600 px-3 py-2 text-sm text-white transition hover:bg-blue-700 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        @click="handleCreate"
      >
        <Plus class="h-4 w-4" />
        {{ t('session.terminal.createTab') }}
      </button>
    </div>

    <div class="flex min-h-0 flex-1 flex-col gap-3 p-4 pt-2">
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
        class="grid gap-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900"
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
        {{ t('session.list.empty') }}
      </p>
      <div v-else class="flex min-h-0 flex-1 flex-col gap-3">
        <label class="relative block">
          <Search class="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            v-model.trim="query"
            class="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none transition focus:border-blue-500"
            :placeholder="t('session.list.searchPlaceholder')"
          />
        </label>

        <div class="min-h-0 flex-1 overflow-auto pr-1">
          <TreeRoot
            v-model="selectedTreeNodes"
            v-model:expanded="expandedTreeKeys"
            :items="treeNodes"
            :default-value="[]"
            :default-expanded="defaultExpandedTreeKeys"
            multiple
            :get-key="(node: SessionTreeNode) => node.id"
            :get-children="(node: SessionTreeNode) => node.children"
            selection-behavior="replace"
            class="grid gap-0.5 outline-none"
          >
            <template #default="{ flattenItems }">
              <TreeItem
                v-for="item in flattenItems"
                :key="item._id"
                v-slot="{ isExpanded }"
                v-bind="item.bind"
                as-child
                @select.prevent="handleTreeSelect(item.value)"
              >
                <div
                  class="group flex w-full items-center gap-2 rounded-lg py-1.5 pr-2 text-left text-sm transition focus:outline-none"
                  :class="
                    isSelectedNode(item.value)
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'
                  "
                  :style="{ paddingLeft: `${(item.level - 1) * 16 + 8}px` }"
                >
                  <span class="inline-flex h-4 w-4 shrink-0 items-center justify-center">
                    <ChevronDown v-if="item.value.children?.length && isExpanded" class="h-4 w-4" />
                    <ChevronRight
                      v-else-if="item.value.children?.length"
                      class="h-4 w-4"
                    />
                  </span>
                  <component
                    :is="environmentLogo(item.value.host)"
                    v-if="item.value.kind === 'environment' && environmentLogo(item.value.host)"
                    class="shrink-0"
                  />
                  <Folder
                    v-if="item.value.kind === 'workspace'"
                    class="h-4 w-4 shrink-0 text-slate-400"
                  />
                  <SquareTerminal
                    v-if="item.value.kind === 'session'"
                    class="h-4 w-4 shrink-0 text-slate-400"
                  />
                  <span
                    class="min-w-0 flex-1 truncate"
                    :class="item.value.kind === 'workspace' ? 'max-w-36' : ''"
                    :title="item.value.kind === 'workspace' ? item.value.label : undefined"
                  >
                    {{ item.value.label }}
                  </span>
                  <span
                    v-if="item.value.kind === 'workspace'"
                    class="ml-auto inline-flex shrink-0 items-center gap-1 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100"
                  >
                    <button
                      type="button"
                      class="inline-flex h-6 w-6 items-center justify-center rounded text-slate-300 transition hover:bg-blue-50 hover:text-blue-600 focus:opacity-100"
                      :aria-label="t('session.workspace.createLabel')"
                      :title="t('session.workspace.createLabel')"
                      @click="createFromWorkspace($event, item.value)"
                    >
                      <Plus class="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      class="inline-flex h-6 w-6 items-center justify-center rounded text-slate-300 transition hover:bg-red-50 hover:text-red-600 focus:opacity-100"
                      :aria-label="t('session.workspace.deleteLabel')"
                      :title="t('session.workspace.deleteLabel')"
                      @click="removeWorkspace($event, item.value)"
                    >
                      <Trash2 class="h-4 w-4" />
                    </button>
                  </span>
                  <span
                    v-if="item.value.session"
                    class="inline-flex shrink-0 items-center gap-1"
                  >
                    <button
                      v-if="item.value.session.status === 'running'"
                      type="button"
                      class="relative inline-flex h-6 w-6 items-center justify-center rounded text-slate-400 transition hover:bg-amber-50 hover:text-amber-600"
                      :aria-label="t('session.card.stopLabel')"
                      :title="t('session.card.stopLabel')"
                      @click="stopSession($event, item.value.session)"
                    >
                      <Ban class="h-4 w-4" />
                    </button>
                    <span
                      v-if="item.value.session.status === 'stopped' && isStartingSession(item.value.session)"
                      class="inline-flex h-6 w-6 items-center justify-center rounded text-slate-400"
                      :aria-label="t('session.card.startLabel')"
                      :title="t('session.card.startLabel')"
                    >
                      <Loader2 class="h-4 w-4 animate-spin" />
                    </span>
                    <button
                      v-if="item.value.session.status === 'stopped'"
                      type="button"
                      class="inline-flex h-6 w-6 items-center justify-center rounded text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                      :aria-label="t('session.card.deleteLabel')"
                      :title="t('session.card.deleteLabel')"
                      @click="removeSession($event, item.value.session)"
                    >
                      <Trash2 class="h-4 w-4" />
                    </button>
                  </span>
                </div>
              </TreeItem>
            </template>
          </TreeRoot>
        </div>
      </div>
    </div>

    <div class="mt-auto flex items-center justify-between gap-3 border-t border-slate-200 p-3 dark:border-slate-800">
      <DropdownMenuRoot>
        <DropdownMenuTrigger
          class="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-slate-600 transition hover:bg-slate-50 hover:text-slate-950 focus:outline-none"
        >
          <Settings class="h-4 w-4" />
          {{ t('app.settings.trigger') }}
        </DropdownMenuTrigger>
        <DropdownMenuPortal>
          <DropdownMenuContent
            :side-offset="8"
            align="start"
            side="top"
            class="z-50 min-w-56 rounded-xl border border-slate-200 bg-white p-1 text-sm text-slate-700 shadow-xl shadow-blue-900/10"
          >
            <DropdownMenuLabel class="px-3 py-2 text-sm uppercase tracking-wide text-slate-400">
              {{ t('app.settings.navigation') }}
            </DropdownMenuLabel>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
              @select="emit('navigate', '/environment')"
            >
              <span class="inline-flex items-center gap-2">
                <LaptopMinimal class="h-4 w-4 text-slate-500 dark:text-slate-400" />
                {{ t('app.nav.environment') }}
              </span>
              <ChevronRight class="h-4 w-4 text-slate-400" />
            </DropdownMenuItem>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
              @select="emit('navigate', '/shortcuts')"
            >
              <span class="inline-flex items-center gap-2">
                <SquareTerminal class="h-4 w-4 text-slate-500" />
                {{ t('app.nav.shortcuts') }}
              </span>
              <ChevronRight class="h-4 w-4 text-slate-400" />
            </DropdownMenuItem>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-amber-700 outline-none hover:bg-amber-50 focus:bg-amber-50"
              @select="emit('closeAll')"
            >
              <span class="inline-flex items-center gap-2">
                <XCircle class="h-4 w-4" />
                {{ t('app.settings.closeAllSessions') }}
              </span>
            </DropdownMenuItem>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger
                class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
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
                  class="z-50 min-w-40 rounded-xl border border-slate-200 bg-white p-1 text-sm text-slate-700 shadow-xl shadow-blue-900/10 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
                >
                  <DropdownMenuRadioGroup v-model="theme.mode">
                    <DropdownMenuRadioItem
                      value="light"
                      class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
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
                      class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
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
                class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-slate-800 dark:focus:bg-slate-800"
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
                  class="z-50 min-w-40 rounded-xl border border-slate-200 bg-white p-1 text-sm text-slate-700 shadow-xl shadow-blue-900/10"
                >
                  <DropdownMenuRadioGroup v-model="locale">
                    <DropdownMenuRadioItem
                      value="zh-CN"
                      class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
                    >
                      <Check
                        :class="locale === 'zh-CN' ? 'opacity-100' : 'opacity-0'"
                        class="h-4 w-4 text-blue-600"
                      />
                      {{ t('app.language.zhCN') }}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem
                      value="en-US"
                      class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
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
      <span v-if="selectedShortcutLabel" class="min-w-0 truncate text-sm text-slate-500">
        {{ t('session.card.shortcut', { shortcut: selectedShortcutLabel }) }}
      </span>
    </div>
  </section>
</template>
