<script setup lang="ts">
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  Languages,
  Loader2,
  Plus,
  Search,
  Settings,
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
} from 'reka-ui'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  EnvironmentSummary,
  Session,
  SessionEnvironment,
  SessionWorkspace,
} from '../types/sessions'
import SessionCard from './SessionCard.vue'

const { locale, t } = useI18n()
const query = ref('')
const expanded = ref(new Set<string>())

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
}>()

const emit = defineEmits<{
  create: []
  collapse: []
  select: [session: Session]
  restart: [session: Session]
  stop: [session: Session]
  remove: [session: Session]
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

function matches(...values: string[]) {
  const needle = values.pop() || ''
  return values.some((value) => value.toLowerCase().includes(needle))
}

function nodeKey(kind: string, id: string) {
  return `${kind}:${id}`
}

function isExpanded(kind: string, id: string) {
  return query.value.trim() ? true : expanded.value.has(nodeKey(kind, id))
}

function toggle(kind: string, id: string) {
  const key = nodeKey(kind, id)
  const next = new Set(expanded.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expanded.value = next
}
</script>

<template>
  <section
    class="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-blue-900/5"
  >
    <div class="flex items-center justify-between gap-3 p-4 pb-2">
      <h2 class="text-lg font-semibold text-slate-950">{{ t('session.list.title') }}</h2>
      <button
        type="button"
        :disabled="!hasReadyEnvironment"
        class="inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-blue-600 px-3 py-2 text-sm text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
        @click="emit('create')"
      >
        <Plus class="h-4 w-4" />
        {{ t('session.list.createLabel') }}
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
      <p v-else-if="sessions.length === 0" class="text-sm text-slate-500">
        {{ t('session.list.empty') }}
      </p>
      <div v-else class="flex min-h-0 flex-1 flex-col gap-3">
        <label class="relative block">
          <Search class="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            v-model.trim="query"
            class="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
            :placeholder="t('session.list.searchPlaceholder')"
          />
        </label>

        <div class="min-h-0 flex-1 overflow-auto pr-1">
          <div v-for="environment in filteredTree" :key="environment.host" class="mb-2">
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              @click="toggle('environment', environment.host)"
            >
              <ChevronDown v-if="isExpanded('environment', environment.host)" class="h-4 w-4" />
              <ChevronRight v-else class="h-4 w-4" />
              <span class="truncate">{{ environment.label }}</span>
              <span class="ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{{
                environment.workspaces.length
              }}</span>
            </button>

            <div
              v-if="isExpanded('environment', environment.host)"
              class="ml-3 border-l border-slate-100 pl-2"
            >
              <div v-for="workspace in environment.workspaces" :key="workspace.id" class="mb-2">
                <button
                  type="button"
                  class="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm text-slate-600 transition hover:bg-slate-50"
                  @click="toggle('workspace', workspace.id)"
                >
                  <ChevronDown v-if="isExpanded('workspace', workspace.id)" class="h-4 w-4" />
                  <ChevronRight v-else class="h-4 w-4" />
                  <span class="min-w-0 flex-1">
                    <span class="block truncate font-medium text-slate-800">{{
                      workspace.name
                    }}</span>
                    <span v-if="!compact" class="block truncate text-xs text-slate-400">{{
                      workspace.path
                    }}</span>
                  </span>
                  <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{{
                    workspace.entries.length
                  }}</span>
                </button>

                <div v-if="isExpanded('workspace', workspace.id)" class="grid gap-2 py-1 pl-4">
                  <SessionCard
                    v-for="session in workspace.entries"
                    :key="session.id"
                    :session="session"
                    :active="session.id === activeSessionId"
                    :compact="compact"
                    @select="emit('select', $event)"
                    @restart="emit('restart', $event)"
                    @stop="emit('stop', $event)"
                    @remove="emit('remove', $event)"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-auto border-t border-slate-200 p-3">
      <DropdownMenuRoot>
        <DropdownMenuTrigger
          class="inline-flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-slate-600 transition hover:bg-slate-50 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
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
              {{ t('app.nav.environment') }}
              <ChevronRight class="h-4 w-4 text-slate-400" />
            </DropdownMenuItem>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
              @select="emit('navigate', '/shortcuts')"
            >
              {{ t('app.nav.shortcuts') }}
              <ChevronRight class="h-4 w-4 text-slate-400" />
            </DropdownMenuItem>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger
                class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
              >
                <span class="inline-flex items-center gap-2">
                  <Languages class="h-4 w-4 text-slate-500" />
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
    </div>
  </section>
</template>
