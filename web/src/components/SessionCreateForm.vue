<script setup lang="ts">
import {
  ComboboxAnchor,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxItemIndicator,
  ComboboxRoot,
  ComboboxTrigger,
  ComboboxViewport,
  SelectContent,
  SelectItem,
  SelectItemText,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { Check, ChevronDown, FolderOpen, Loader2 } from '@lucide/vue'
import { computed, reactive, ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { listShortcuts } from '../api/sessions'
import { fieldErrorClass, fieldErrorMessageClass, fieldErrorWithinClass } from '../formValidation'
import type {
  CreateSessionPayload,
  EnvironmentSummary,
  Shortcut,
  ShortcutHost,
} from '../types/sessions'
import WorkspaceBrowser from './WorkspaceBrowser.vue'

const { t } = useI18n()
type FieldName = 'workspace' | 'name' | 'host' | 'shortcut_id'

const props = defineProps<{
  environments: EnvironmentSummary[]
  submitting: boolean
  initialHost?: ShortcutHost
  initialWorkspace?: string
  initialShortcutId?: string
}>()
const emit = defineEmits<{
  create: [payload: CreateSessionPayload]
  cancel: []
}>()

const hosts: ShortcutHost[] = ['windows_cygwin', 'windows_wsl', 'linux']
const selectedHost = ref<ShortcutHost>(props.initialHost || 'windows_cygwin')
const shortcuts = ref<Shortcut[]>([])
const shortcutError = ref('')
const submitted = ref(false)
const form = reactive<CreateSessionPayload>({
  name: '',
  workspace: props.initialWorkspace || '',
  shortcut_id: props.initialShortcutId || '',
})
const loadingShortcuts = ref(false)
const showWorkspaceBrowser = ref(false)
const shortcutComboboxOpen = ref(false)
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
const selectedShortcut = computed(() =>
  filteredShortcuts.value.find((shortcut) => shortcut.id === form.shortcut_id),
)
const validationErrors = computed<Record<FieldName, string>>(() => ({
  workspace: form.workspace ? '' : t('session.create.validation.workspaceRequired'),
  name: form.name ? '' : t('session.create.validation.nameRequired'),
  host: availableHosts.value.includes(selectedHost.value)
    ? ''
    : t('session.create.validation.hostReadyRequired'),
  shortcut_id: form.shortcut_id ? '' : t('session.create.validation.shortcutRequired'),
}))
const fieldErrors = computed<Record<FieldName, string>>(() => {
  if (!submitted.value) {
    return emptyFieldErrors()
  }
  return validationErrors.value
})

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

watch(
  () => props.initialShortcutId,
  (shortcutId) => {
    form.shortcut_id = shortcutId || ''
  },
)

watch([availableHosts, filteredShortcuts], () => {
  if (!availableHosts.value.includes(selectedHost.value)) {
    selectedHost.value = availableHosts.value[0] || 'windows_cygwin'
  }
  if (!filteredShortcuts.value.some((shortcut) => shortcut.id === form.shortcut_id)) {
    form.shortcut_id = props.initialShortcutId && filteredShortcuts.value.some((shortcut) => shortcut.id === props.initialShortcutId)
      ? props.initialShortcutId
      : filteredShortcuts.value[0]?.id || ''
  }
})

onMounted(loadShortcuts)

async function loadShortcuts() {
  loadingShortcuts.value = true
  try {
    const response = await listShortcuts()
    shortcuts.value = response.shortcuts
    form.shortcut_id = props.initialShortcutId && filteredShortcuts.value.some((shortcut) => shortcut.id === props.initialShortcutId)
      ? props.initialShortcutId
      : filteredShortcuts.value[0]?.id || ''
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
  if (!validate()) {
    return
  }

  emit('create', {
    name: form.name,
    workspace: form.workspace,
    shortcut_id: form.shortcut_id,
  })
}

function validate(): boolean {
  submitted.value = true
  return !Object.values(validationErrors.value).some(Boolean)
}

function emptyFieldErrors(): Record<FieldName, string> {
  return {
    workspace: '',
    name: '',
    host: '',
    shortcut_id: '',
  }
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
      <h2 class="text-lg font-semibold text-slate-950 dark:text-slate-100">{{ t('session.create.title') }}</h2>
    </div>

    <p v-if="shortcutError" class="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
      {{ shortcutError }}
    </p>

    <div class="grid gap-2 text-sm text-slate-700 dark:text-slate-300">
      <span>{{ t('session.create.workspace') }}</span>
      <div class="flex gap-2">
        <input
          v-model.trim="form.workspace"
          class="min-w-0 flex-1 rounded-md border border-slate-300 bg-white/60 px-3 py-2 outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
          :class="fieldErrors.workspace ? fieldErrorClass : ''"
          :aria-invalid="!!fieldErrors.workspace"
          :aria-describedby="fieldErrors.workspace ? 'session-workspace-error' : undefined"
          :placeholder="t('session.create.workspacePlaceholder')"
        />
        <button
          type="button"
          class="inline-flex items-center justify-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
          @click="showWorkspaceBrowser = !showWorkspaceBrowser"
        >
          <FolderOpen class="h-4 w-4" />
          {{ showWorkspaceBrowser ? t('session.create.collapse') : t('session.create.browse') }}
        </button>
      </div>
      <p v-if="fieldErrors.workspace" id="session-workspace-error" :class="fieldErrorMessageClass">
        {{ fieldErrors.workspace }}
      </p>
      <WorkspaceBrowser
        v-if="showWorkspaceBrowser"
        :selected-path="form.workspace"
        @select="selectWorkspace"
      />
    </div>

    <label class="grid gap-2 text-sm text-slate-700 dark:text-slate-300">
      {{ t('session.create.name') }}
      <input
        v-model.trim="form.name"
        class="rounded-md border border-slate-300 bg-white/60 px-3 py-2 outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
        :class="fieldErrors.name ? fieldErrorClass : ''"
        :aria-invalid="!!fieldErrors.name"
        :aria-describedby="fieldErrors.name ? 'session-name-error' : undefined"
        :placeholder="t('session.create.namePlaceholder')"
      />
      <span v-if="fieldErrors.name" id="session-name-error" :class="fieldErrorMessageClass">
        {{ fieldErrors.name }}
      </span>
    </label>

    <label class="grid gap-2 text-sm text-slate-700 dark:text-slate-300">
      {{ t('session.create.host') }}
      <SelectRoot v-model="selectedHost">
        <SelectTrigger
          class="flex items-center justify-between rounded-md border border-slate-300 bg-white/60 px-3 py-2 text-left outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
          :class="fieldErrors.host ? fieldErrorClass : ''"
          :aria-invalid="!!fieldErrors.host"
          :aria-describedby="fieldErrors.host ? 'session-host-error' : undefined"
        >
          <SelectValue />
          <ChevronDown class="h-4 w-4 shrink-0 text-slate-400 dark:text-slate-500" />
        </SelectTrigger>
        <SelectContent
          position="popper"
          class="z-50 min-w-[var(--reka-select-trigger-width)] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg shadow-blue-900/5 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:shadow-none"
        >
          <SelectViewport class="p-1">
            <SelectItem
              v-for="host in hosts"
              :key="host"
              :value="host"
              :disabled="!availableHosts.includes(host)"
              :text-value="`${hostLabel(host)}${hostDisabledReason(host) ? ` - ${hostDisabledReason(host)}` : ''}`"
              class="cursor-pointer rounded-md px-3 py-2 text-sm outline-none hover:bg-blue-50 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50 data-[highlighted]:bg-blue-50 dark:hover:bg-slate-800 dark:data-[highlighted]:bg-slate-800"
            >
              <SelectItemText>
                {{ hostLabel(host)
                }}{{ hostDisabledReason(host) ? ` - ${hostDisabledReason(host)}` : '' }}
              </SelectItemText>
            </SelectItem>
          </SelectViewport>
        </SelectContent>
      </SelectRoot>
      <span v-if="fieldErrors.host" id="session-host-error" :class="fieldErrorMessageClass">
        {{ fieldErrors.host }}
      </span>
    </label>

    <label class="grid gap-2 text-sm text-slate-700 dark:text-slate-300">
      {{ t('session.create.shortcut') }}
      <p v-if="loadingShortcuts" class="inline-flex items-center gap-2 text-sm text-slate-500">
        <Loader2 class="h-4 w-4 animate-spin" />
        {{ t('session.create.loadingShortcuts') }}
      </p>
      <p v-else-if="filteredShortcuts.length === 0" class="text-sm text-amber-700">
        {{ t('session.create.noShortcutsForHost') }}
      </p>
      <ComboboxRoot
        v-else
        v-model="form.shortcut_id"
        v-model:open="shortcutComboboxOpen"
        open-on-click
        open-on-focus
        reset-search-term-on-select
      >
        <ComboboxAnchor
          class="flex items-center rounded-md border border-slate-300 bg-white/60 outline-none transition focus-within:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:focus-within:border-blue-500"
          :class="fieldErrors.shortcut_id ? fieldErrorWithinClass : ''"
          :aria-invalid="!!fieldErrors.shortcut_id"
          :aria-describedby="fieldErrors.shortcut_id ? 'session-shortcut-error' : undefined"
        >
          <ComboboxInput
            class="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm text-slate-700 outline-none placeholder:text-slate-400 dark:text-slate-200 dark:placeholder:text-slate-500"
            :display-value="() => selectedShortcut?.name || ''"
          />
          <ComboboxTrigger class="inline-flex h-full shrink-0 items-center px-3 text-slate-400 transition hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300">
            <ChevronDown class="h-4 w-4" />
          </ComboboxTrigger>
        </ComboboxAnchor>
        <ComboboxContent
          position="popper"
          class="z-50 max-h-64 w-[var(--reka-combobox-trigger-width)] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg shadow-blue-900/5 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:shadow-none"
        >
          <ComboboxViewport class="p-1">
            <ComboboxEmpty class="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">
              {{ t('session.create.noShortcutsForHost') }}
            </ComboboxEmpty>
            <ComboboxItem
              v-for="shortcut in filteredShortcuts"
              :key="shortcut.id"
              :value="shortcut.id"
              :text-value="shortcut.name"
              class="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm outline-none hover:bg-blue-50 data-[highlighted]:bg-blue-50 dark:hover:bg-slate-800 dark:data-[highlighted]:bg-slate-800"
            >
              <span>{{ shortcut.name }}</span>
              <ComboboxItemIndicator>
                <Check class="h-4 w-4 text-blue-600 dark:text-blue-300" />
              </ComboboxItemIndicator>
            </ComboboxItem>
          </ComboboxViewport>
        </ComboboxContent>
      </ComboboxRoot>
      <span v-if="fieldErrors.shortcut_id" id="session-shortcut-error" :class="fieldErrorMessageClass">
        {{ fieldErrors.shortcut_id }}
      </span>
    </label>

    <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button
        type="button"
        :disabled="props.submitting"
        class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
        @click="emit('cancel')"
      >
        {{ t('app.actions.cancel') }}
      </button>
      <button
        type="submit"
        :disabled="props.submitting"
        class="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white transition hover:bg-blue-700 disabled:opacity-60"
      >
        <Loader2 v-if="props.submitting" class="h-4 w-4 animate-spin" />
        {{ props.submitting ? t('session.create.submitting') : t('session.create.submit') }}
      </button>
    </div>
  </form>
</template>
