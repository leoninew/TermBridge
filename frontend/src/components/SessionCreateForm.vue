<script setup lang="ts">
import {
  SelectContent,
  SelectItem,
  SelectItemText,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { FolderOpen, Loader2 } from '@lucide/vue'
import { computed, reactive, ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { listShortcuts } from '../api/sessions'
import type {
  CreateSessionPayload,
  EnvironmentSummary,
  Shortcut,
  ShortcutHost,
} from '../types/sessions'
import WorkspaceBrowser from './WorkspaceBrowser.vue'

const { t } = useI18n()
const props = defineProps<{
  environments: EnvironmentSummary[]
  submitting: boolean
  error: string
  initialHost?: ShortcutHost
  initialWorkspace?: string
}>()
const emit = defineEmits<{
  create: [payload: CreateSessionPayload]
  cancel: []
}>()

const hosts: ShortcutHost[] = ['windows_cygwin', 'windows_wsl', 'linux']
const selectedHost = ref<ShortcutHost>(props.initialHost || 'windows_cygwin')
const shortcuts = ref<Shortcut[]>([])
const shortcutError = ref('')
const form = reactive<CreateSessionPayload>({
  name: '',
  workspace: props.initialWorkspace || '',
  shortcut_id: '',
})
const loadingShortcuts = ref(false)
const showWorkspaceBrowser = ref(false)
const environmentsByHost = computed(
  () => new Map(props.environments.map((environment) => [environment.host, environment])),
)
const availableHosts = computed(() =>
  hosts.filter((host) => {
    const environment = environmentsByHost.value.get(host)
    return environment?.available_on_host && environment.readiness === 'ready'
  }),
)
const filteredShortcuts = computed(() =>
  shortcuts.value.filter((shortcut) => shortcut.host === selectedHost.value),
)

watch(
  () => props.initialHost,
  (host) => {
    if (host) {
      selectedHost.value = host
    }
  },
)

watch(
  () => props.initialWorkspace,
  (workspace) => {
    form.workspace = workspace || ''
  },
)

watch([availableHosts, filteredShortcuts], () => {
  if (!availableHosts.value.includes(selectedHost.value)) {
    selectedHost.value = availableHosts.value[0] || 'windows_cygwin'
  }
  if (!filteredShortcuts.value.some((shortcut) => shortcut.id === form.shortcut_id)) {
    form.shortcut_id = filteredShortcuts.value[0]?.id || ''
  }
})

onMounted(loadShortcuts)

async function loadShortcuts() {
  loadingShortcuts.value = true
  try {
    const response = await listShortcuts()
    shortcuts.value = response.shortcuts
    form.shortcut_id = filteredShortcuts.value[0]?.id || ''
  } catch (err) {
    shortcutError.value =
      err instanceof Error ? err.message : t('session.create.loadShortcutsError')
  } finally {
    loadingShortcuts.value = false
  }
}

function selectWorkspace(path: string) {
  form.workspace = path
}

async function submit() {
  emit('create', {
    name: form.name,
    workspace: form.workspace,
    shortcut_id: form.shortcut_id,
  })
}

function hostLabel(host: ShortcutHost): string {
  return t(`hosts.${host}`)
}

function hostDisabledReason(host: ShortcutHost): string {
  const environment = environmentsByHost.value.get(host)
  if (!environment?.available_on_host) {
    return t('session.create.hostUnavailable')
  }
  if (environment.readiness !== 'ready') {
    return t('session.create.hostNotReady')
  }
  return ''
}
</script>

<template>
  <form class="grid gap-5" @submit.prevent="submit">
    <div>
      <h2 class="text-lg font-semibold text-slate-950">{{ t('session.create.title') }}</h2>
    </div>

    <p v-if="props.error" class="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
      {{ props.error }}
    </p>

    <p v-if="shortcutError" class="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
      {{ shortcutError }}
    </p>

    <div class="grid gap-2 text-sm text-slate-700">
      <span>{{ t('session.create.workspace') }}</span>
      <div class="flex gap-2">
        <input
          v-model.trim="form.workspace"
          required
          class="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500"
          :placeholder="t('session.create.workspacePlaceholder')"
        />
        <button
          type="button"
          class="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
          @click="showWorkspaceBrowser = !showWorkspaceBrowser"
        >
          <FolderOpen class="h-4 w-4" />
          {{ showWorkspaceBrowser ? t('session.create.collapse') : t('session.create.browse') }}
        </button>
      </div>
      <WorkspaceBrowser
        v-if="showWorkspaceBrowser"
        :selected-path="form.workspace"
        @select="selectWorkspace"
      />
    </div>

    <label class="grid gap-2 text-sm text-slate-700">
      {{ t('session.create.name') }}
      <input
        v-model.trim="form.name"
        required
        class="rounded-xl border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500"
        :placeholder="t('session.create.namePlaceholder')"
      />
    </label>

    <label class="grid gap-2 text-sm text-slate-700">
      {{ t('session.create.host') }}
      <select
        v-model="selectedHost"
        class="rounded-xl border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500"
      >
        <option
          v-for="host in hosts"
          :key="host"
          :value="host"
          :disabled="!availableHosts.includes(host)"
        >
          {{ hostLabel(host)
          }}{{ hostDisabledReason(host) ? ` - ${hostDisabledReason(host)}` : '' }}
        </option>
      </select>
    </label>

    <label class="grid gap-2 text-sm text-slate-700">
      {{ t('session.create.shortcut') }}
      <p v-if="loadingShortcuts" class="inline-flex items-center gap-2 text-sm text-slate-500">
        <Loader2 class="h-4 w-4 animate-spin" />
        {{ t('session.create.loadingShortcuts') }}
      </p>
      <p v-else-if="filteredShortcuts.length === 0" class="text-sm text-amber-700">
        {{ t('session.create.noShortcutsForHost') }}
      </p>
      <SelectRoot v-else v-model="form.shortcut_id" required>
        <SelectTrigger
          class="flex items-center justify-between rounded-xl border border-slate-300 bg-white px-3 py-2 text-left outline-none transition focus:border-blue-500"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent
          class="z-50 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
        >
          <SelectViewport class="p-1">
            <SelectItem
              v-for="shortcut in filteredShortcuts"
              :key="shortcut.id"
              :value="shortcut.id"
              class="cursor-pointer rounded-lg px-3 py-2 text-sm outline-none hover:bg-blue-50 data-[highlighted]:bg-blue-50"
            >
              <SelectItemText>{{ shortcut.name }}</SelectItemText>
            </SelectItem>
          </SelectViewport>
        </SelectContent>
      </SelectRoot>
    </label>

    <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button
        type="button"
        :disabled="props.submitting"
        class="rounded-xl border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
        @click="emit('cancel')"
      >
        {{ t('app.actions.cancel') }}
      </button>
      <button
        type="submit"
        :disabled="props.submitting || !form.shortcut_id || !availableHosts.includes(selectedHost)"
        class="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-60"
      >
        <Loader2 v-if="props.submitting" class="h-4 w-4 animate-spin" />
        {{ props.submitting ? t('session.create.submitting') : t('session.create.submit') }}
      </button>
    </div>
  </form>
</template>
