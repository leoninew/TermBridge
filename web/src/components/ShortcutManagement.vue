<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ChevronDown, Loader2, Plus } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import {
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
  DialogClose,
  DialogContent,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
  SelectContent,
  SelectItem,
  SelectItemText,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import CygwinLogo from './CygwinLogo.vue'
import LinuxLogo from './LinuxLogo.vue'
import WslLogo from './WslLogo.vue'
import { useToastStore } from '../stores/toast'
import {
  createShortcut,
  deleteShortcut,
  listEnvironments,
  listShortcuts,
  updateShortcut,
} from '../api/sessions'
import type {
  CreateShortcutPayload,
  EnvironmentSummary,
  Session,
  Shortcut,
  ShortcutHost,
} from '../types/sessions'

const { t } = useI18n()
const toast = useToastStore()
const props = defineProps<{
  sessions: Session[]
}>()
const emit = defineEmits<{
  createSession: [context: { host: ShortcutHost; shortcutId: string }]
}>()
const hosts: ShortcutHost[] = ['windows_cygwin', 'windows_wsl', 'linux']
const shortcuts = ref<Shortcut[]>([])
const environments = ref<EnvironmentSummary[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const editingId = ref<string>()
const showModal = ref(false)
const deletingShortcut = ref<Shortcut>()
const deleteDialogOpen = computed({
  get: () => !!deletingShortcut.value,
  set: (open: boolean) => {
    if (!open) {
      deletingShortcut.value = undefined
    }
  },
})
const usedShortcutIds = computed(
  () =>
    new Set(
      props.sessions
        .map((session) => session.shortcut_id)
        .filter((shortcutId): shortcutId is string => !!shortcutId),
    ),
)
const environmentsByHost = computed(
  () => new Map(environments.value.map((environment) => [environment.host, environment])),
)
const shortcutGroups = computed(() =>
  hosts
    .map((host) => ({
      host,
      shortcuts: shortcuts.value.filter((shortcut) => shortcut.host === host),
    }))
    .filter((group) => group.shortcuts.length > 0),
)

const form = reactive<{
  name: string
  command: string
  host: ShortcutHost | ''
  description: string
}>({
  name: '',
  command: '',
  host: '',
  description: '',
})

onMounted(load)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [shortcutResponse, environmentResponse] = await Promise.all([
      listShortcuts(),
      listEnvironments(),
    ])
    shortcuts.value = shortcutResponse.shortcuts
    environments.value = environmentResponse.environments
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('shortcutManagement.errors.load')
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  resetForm()
  showModal.value = true
}

function edit(shortcut: Shortcut) {
  editingId.value = shortcut.id
  form.name = shortcut.name
  form.command = shortcut.command
  form.host = shortcut.host
  form.description = shortcut.description || ''
  showModal.value = true
}

function resetForm() {
  editingId.value = undefined
  form.name = ''
  form.command = ''
  form.host = ''
  form.description = ''
}

function closeModal() {
  showModal.value = false
  resetForm()
}

async function saveShortcut() {
  error.value = ''
  saving.value = true
  try {
    const payload = normalizePayload()
    const updating = !!editingId.value
    if (editingId.value) {
      await updateShortcut(editingId.value, payload)
    } else {
      await createShortcut(payload)
    }
    closeModal()
    await load()
    toast.show({
      title: t(updating ? 'shortcutManagement.success.updated' : 'shortcutManagement.success.created'),
      variant: 'success',
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('shortcutManagement.errors.save')
  } finally {
    saving.value = false
  }
}

function createSessionFromShortcut(shortcut: Shortcut) {
  emit('createSession', { host: shortcut.host, shortcutId: shortcut.id })
}

function askRemoveShortcut(shortcut: Shortcut) {
  if (usedShortcutIds.value.has(shortcut.id)) {
    return
  }
  deletingShortcut.value = shortcut
}

async function confirmRemoveShortcut() {
  if (!deletingShortcut.value) {
    return
  }
  error.value = ''
  try {
    await deleteShortcut(deletingShortcut.value.id)
    deletingShortcut.value = undefined
    await load()
    toast.show({ title: t('shortcutManagement.success.deleted'), variant: 'success' })
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('shortcutManagement.errors.delete')
  }
}

function normalizePayload(): CreateShortcutPayload {
  if (!form.host) {
    throw new Error(t('shortcutManagement.errors.hostRequired'))
  }
  return {
    name: form.name.trim(),
    command: form.command.trim(),
    host: form.host,
    description: form.description?.trim() || null,
  }
}

function hostLabel(host: ShortcutHost): string {
  return t(`hosts.${host}`)
}

function hostLogo(host: ShortcutHost) {
  if (host === 'windows_cygwin') {
    return CygwinLogo
  }
  if (host === 'windows_wsl') {
    return WslLogo
  }
  return LinuxLogo
}

function hostDisabledReason(host: ShortcutHost): string {
  const environment = environmentsByHost.value.get(host)
  if (!environment?.available_on_host) {
    return t('shortcutManagement.hostDisabled.unavailable')
  }
  return ''
}
</script>

<template>
  <section
    class="flex h-full min-h-0 flex-col gap-4 bg-slate-100 p-4 text-slate-900 dark:bg-slate-950 dark:text-slate-100"
  >
    <div class="flex items-start justify-between gap-3 border-b border-slate-200 pb-3 dark:border-slate-800">
      <div>
        <h2 class="text-lg font-semibold text-slate-950 dark:text-slate-100">{{ t('shortcutManagement.title') }}</h2>
      </div>
      <button
        class="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm text-white transition hover:bg-blue-700"
        @click="openCreateModal"
      >
        <Plus class="h-4 w-4" />
        {{ t('shortcutManagement.actions.create') }}
      </button>
    </div>

    <p v-if="error" class="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <p v-if="loading" class="inline-flex items-center gap-2 text-sm text-slate-500">
      <Loader2 class="h-4 w-4 animate-spin" />
      {{ t('shortcutManagement.loading') }}
    </p>

    <div class="grid min-h-0 flex-1 content-start gap-4 overflow-auto pr-1">
      <section v-for="group in shortcutGroups" :key="group.host" class="grid gap-2.5">
        <div class="flex items-center gap-2 border-b border-slate-200 pb-2 dark:border-slate-800">
          <component :is="hostLogo(group.host)" class="shrink-0" />
          <h3 class="text-sm font-semibold text-slate-950 dark:text-slate-100">{{ hostLabel(group.host) }}</h3>
        </div>

        <div class="grid gap-2.5 md:grid-cols-3 xl:grid-cols-4">
          <article
            v-for="shortcut in group.shortcuts"
            :key="shortcut.id"
            class="group relative flex flex-col justify-between border border-slate-200 bg-white/35 p-2.5 pb-12 transition hover:border-blue-400 hover:bg-white/70 dark:border-slate-800 dark:bg-slate-950 dark:hover:border-blue-500 dark:hover:bg-slate-900/50"
          >
            <div>
              <p class="truncate text-sm font-semibold text-slate-950 dark:text-slate-100">{{ shortcut.name }}</p>
              <p
                class="mt-1.5 truncate rounded-md border border-slate-300 bg-slate-200/80 px-2 py-1.5 font-mono text-xs text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
                :title="shortcut.command"
              >
                {{ shortcut.command }}
              </p>
            </div>

            <div
              class="absolute bottom-2.5 right-2.5 flex gap-1.5"
            >
              <button
                class="rounded-md border border-blue-200 px-2 py-1 text-sm text-blue-600 opacity-0 transition hover:bg-blue-50 group-hover:opacity-100 group-focus-within:opacity-100 dark:border-blue-900/60 dark:text-blue-400 dark:hover:bg-blue-950/40"
                @click="createSessionFromShortcut(shortcut)"
              >
                {{ t('shortcutManagement.actions.createSession') }}
              </button>
              <button
                class="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                @click="edit(shortcut)"
              >
                {{ t('app.actions.edit') }}
              </button>
              <button
                class="rounded-md border border-red-200 px-2 py-1 text-sm text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-red-900/60 dark:text-red-400 dark:hover:bg-red-950/40"
                :disabled="usedShortcutIds.has(shortcut.id)"
                :title="
                  usedShortcutIds.has(shortcut.id)
                    ? t('shortcutManagement.delete.inUse')
                    : undefined
                "
                @click="askRemoveShortcut(shortcut)"
              >
                {{ t('app.actions.delete') }}
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>

    <DialogRoot v-model:open="showModal">
      <DialogPortal>
        <DialogOverlay class="fixed inset-0 z-50 bg-slate-950/40" />
        <DialogContent
          class="fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border border-slate-200 bg-white p-5 text-sm shadow-xl shadow-blue-900/10 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:shadow-none"
        >
          <div>
            <DialogTitle class="text-lg font-semibold text-slate-950 dark:text-slate-100">
              {{
                editingId
                  ? t('shortcutManagement.dialog.editTitle')
                  : t('shortcutManagement.dialog.createTitle')
              }}
            </DialogTitle>
          </div>

          <form class="grid gap-3" @submit.prevent="saveShortcut">
            <label class="grid gap-1.5 text-sm text-slate-700 dark:text-slate-300">
              {{ t('shortcutManagement.fields.name') }}
              <input
                v-model.trim="form.name"
                required
                class="rounded-md border border-slate-300 bg-white/60 px-3 py-2 outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
              />
            </label>
            <label class="grid gap-1.5 text-sm text-slate-700 dark:text-slate-300">
              {{ t('shortcutManagement.fields.command') }}
              <input
                v-model.trim="form.command"
                required
                class="rounded-md border border-slate-300 bg-white/60 px-3 py-2 font-mono text-xs outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
              />
            </label>
            <label class="grid gap-1.5 text-sm text-slate-700 dark:text-slate-300">
              {{ t('shortcutManagement.fields.host') }}
              <SelectRoot v-model="form.host" required>
                <SelectTrigger
                  class="flex items-center justify-between rounded-md border border-slate-300 bg-white/60 px-3 py-2 text-left outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
                >
                  <SelectValue :placeholder="t('shortcutManagement.fields.selectHost')" />
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
                      :disabled="!!hostDisabledReason(host)"
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
            </label>
            <label class="grid gap-1.5 text-sm text-slate-700 dark:text-slate-300">
              {{ t('shortcutManagement.fields.description') }}
              <textarea
                v-model.trim="form.description"
                rows="3"
                class="rounded-md border border-slate-300 bg-white/60 px-3 py-2 outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
              />
            </label>
            <div class="mt-2 flex justify-end gap-2">
              <DialogClose as-child>
                <button
                  type="button"
                  class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
                >
                  {{ t('app.actions.cancel') }}
                </button>
              </DialogClose>
              <button
                type="submit"
                :disabled="saving"
                class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white transition hover:bg-blue-700 disabled:opacity-60"
              >
                <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
                {{ t('app.actions.save') }}
              </button>
            </div>
          </form>
        </DialogContent>
      </DialogPortal>
    </DialogRoot>

    <AlertDialogRoot v-model:open="deleteDialogOpen">
      <AlertDialogPortal>
        <AlertDialogOverlay class="fixed inset-0 z-50 bg-slate-950/40" />
        <AlertDialogContent
          class="fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border border-slate-200 bg-white p-5 text-sm shadow-xl shadow-blue-900/10 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:shadow-none"
        >
          <div>
            <AlertDialogTitle class="text-lg font-semibold text-slate-950 dark:text-slate-100">
              {{ t('shortcutManagement.delete.title') }}
            </AlertDialogTitle>
            <p class="mt-3 text-sm text-slate-600 dark:text-slate-400">
              {{ t('shortcutManagement.delete.description', { name: deletingShortcut?.name }) }}
            </p>
          </div>
          <div class="flex justify-end gap-2">
            <AlertDialogCancel class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900">
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <AlertDialogAction
              class="rounded-lg bg-red-600 px-4 py-2 text-white transition hover:bg-red-700"
              @click="confirmRemoveShortcut"
            >
              {{ t('app.actions.delete') }}
            </AlertDialogAction>
          </div>
        </AlertDialogContent>
      </AlertDialogPortal>
    </AlertDialogRoot>
  </section>
</template>
