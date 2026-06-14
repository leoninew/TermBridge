<script setup lang="ts">
import { ChevronRight, Folder, HardDrive, Loader2 } from '@lucide/vue'
import { nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getWorkspaceRoots, getWorkspaceTree } from '../api/sessions'
import type { WorkspaceRoot, WorkspaceTreeNode } from '../types/sessions'

interface TreeEntry {
  path: string
  name: string
  kind: 'root' | 'directory'
  depth: number
  hasChildren: boolean
  expanded: boolean
  loading: boolean
  loaded: boolean
}

const { t } = useI18n()
const props = defineProps<{
  selectedPath?: string
}>()

const emit = defineEmits<{
  select: [path: string]
}>()

const entries = ref<TreeEntry[]>([])
const selectedPath = ref(props.selectedPath || '')
const loadingRoots = ref(false)
const error = ref('')
const browserRef = ref()

onMounted(loadRoots)

async function loadRoots() {
  loadingRoots.value = true
  error.value = ''
  try {
    const response = await getWorkspaceRoots()
    entries.value = response.roots.map((root) => rootToEntry(root))
    await expandToSelectedPath()
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('workspace.errors.loadRoots')
  } finally {
    loadingRoots.value = false
  }
}

function rootToEntry(root: WorkspaceRoot): TreeEntry {
  return {
    path: root.path,
    name: root.name,
    kind: 'root',
    depth: 0,
    hasChildren: true,
    expanded: false,
    loading: false,
    loaded: false,
  }
}

function nodeToEntry(node: WorkspaceTreeNode, depth: number): TreeEntry {
  return {
    path: node.path,
    name: node.name,
    kind: 'directory',
    depth,
    hasChildren: node.has_children,
    expanded: false,
    loading: false,
    loaded: false,
  }
}

async function expandToSelectedPath() {
  if (!selectedPath.value) {
    return
  }

  let currentIndex = entries.value.findIndex((entry) =>
    isSameOrParent(entry.path, selectedPath.value),
  )
  while (currentIndex >= 0) {
    const entry = entries.value[currentIndex]
    if (samePath(entry.path, selectedPath.value) || !entry.hasChildren) {
      await scrollSelectedIntoView()
      return
    }
    await expandEntry(entry, currentIndex)
    currentIndex = entries.value.findIndex(
      (candidate, index) =>
        index > currentIndex && isSameOrParent(candidate.path, selectedPath.value),
    )
  }
}

async function expandEntry(entry: TreeEntry, index: number) {
  if (entry.expanded) {
    return
  }
  entry.expanded = true
  if (entry.loaded) {
    return
  }
  entry.loading = true
  try {
    const response = await getWorkspaceTree(entry.path)
    const children = response.children.map((child) => nodeToEntry(child, entry.depth + 1))
    entries.value.splice(index + 1, 0, ...children)
    entry.loaded = true
  } finally {
    entry.loading = false
  }
}

function isSameOrParent(parent: string, child: string): boolean {
  const normalizedParent = normalizePath(parent)
  const normalizedChild = normalizePath(child)
  return normalizedChild === normalizedParent || normalizedChild.startsWith(`${normalizedParent}/`)
}

function samePath(left: string, right: string): boolean {
  return normalizePath(left) === normalizePath(right)
}

function normalizePath(path: string): string {
  return path.replaceAll('\\', '/').replace(/\/+$/, '').toLowerCase()
}

async function scrollSelectedIntoView() {
  await nextTick()
  browserRef.value
    ?.querySelector('[data-selected-workspace="true"]')
    ?.scrollIntoView({ block: 'center' })
}

async function toggle(entry: TreeEntry, index: number) {
  selectedPath.value = entry.path
  emit('select', entry.path)
  if (!entry.hasChildren) {
    return
  }
  if (entry.expanded) {
    collapse(entry, index)
    return
  }
  entry.expanded = true
  if (entry.loaded) {
    return
  }

  entry.loading = true
  error.value = ''
  try {
    const response = await getWorkspaceTree(entry.path)
    const children = response.children.map((child) => nodeToEntry(child, entry.depth + 1))
    entries.value.splice(index + 1, 0, ...children)
    entry.loaded = true
  } catch (err) {
    entry.expanded = false
    error.value = err instanceof Error ? err.message : t('workspace.errors.loadDirectory')
  } finally {
    entry.loading = false
  }
}

function collapse(entry: TreeEntry, index: number) {
  entry.expanded = false
  let removeCount = 0
  for (const child of entries.value.slice(index + 1)) {
    if (child.depth <= entry.depth) {
      break
    }
    removeCount += 1
  }
  entries.value.splice(index + 1, removeCount)
}
</script>

<template>
  <section
    ref="browserRef"
    class="overflow-hidden border border-slate-200 bg-white/35 font-normal dark:border-slate-800 dark:bg-slate-950"
  >
    <div class="max-h-64 overflow-auto p-2">
      <p
        v-if="loadingRoots"
        class="inline-flex items-center gap-2 px-2 py-1 text-sm text-slate-500"
      >
        <Loader2 class="h-4 w-4 animate-spin" />
        {{ t('workspace.loadingRoots') }}
      </p>
      <p v-else-if="error" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
        {{ error }}
      </p>
      <p v-else-if="entries.length === 0" class="px-2 py-1 text-sm text-slate-500">
        {{ t('workspace.empty') }}
      </p>

      <div v-else class="grid gap-1">
        <button
          v-for="(entry, index) in entries"
          :key="entry.path"
          type="button"
          class="flex items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition hover:bg-blue-50 dark:hover:bg-slate-900"
          :class="
            selectedPath === entry.path
              ? 'bg-blue-100 text-blue-800 dark:bg-blue-950/50 dark:text-blue-300'
              : 'text-slate-700 dark:text-slate-300'
          "
          :style="{ paddingLeft: `${8 + entry.depth * 18}px` }"
          :data-selected-workspace="selectedPath === entry.path"
          @click="toggle(entry, index)"
        >
          <Loader2 v-if="entry.loading" class="h-4 w-4 animate-spin text-slate-400" />
          <ChevronRight
            v-else-if="entry.hasChildren"
            class="h-4 w-4 text-slate-400 transition dark:text-slate-500"
            :class="{ 'rotate-90': entry.expanded }"
          />
          <span v-else class="h-4 w-4" />
          <HardDrive
            v-if="entry.kind === 'root'"
            class="h-4 w-4 shrink-0 text-slate-500 dark:text-slate-400"
          />
          <Folder v-else class="h-4 w-4 shrink-0 text-slate-500 dark:text-slate-400" />
          <span class="truncate">{{ entry.name }}</span>
        </button>
      </div>
    </div>
  </section>
</template>
