<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ChevronDown, GripVertical, Loader2, Plus } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import {
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
import { VueDraggable } from 'vue-draggable-plus'
import CygwinLogo from './CygwinLogo.vue'
import LinuxLogo from './LinuxLogo.vue'
import WslLogo from './WslLogo.vue'
import { useToastStore } from '../stores/toast'
import { fieldErrorClass, fieldErrorMessageClass } from '../formValidation'
import {
  createShortcut,
  deleteShortcut,
  listEnvironments,
  listShortcuts,
  reorderShortcuts,
  updateShortcut,
} from '../api/sessions'
import type {
  CreateShortcutPayload,
  EnvironmentSummary,
  Shortcut,
  ShortcutEnvironment,
  ShortcutHost,
} from '../types/sessions'

defineOptions({ inheritAttrs: false })

const { t } = useI18n()
type FieldName = 'name' | 'command' | 'host'
type DragEndEvent = {
  oldIndex?: number
  newIndex?: number
}

const toast = useToastStore()
const emit = defineEmits<{
  createSession: [context: { host: ShortcutHost; shortcutId: string }]
}>()
const hosts: ShortcutHost[] = ['windows_cygwin', 'windows_wsl', 'linux']
const shortcutEnvironments = ref<ShortcutEnvironment[]>([])
const environments = ref<EnvironmentSummary[]>([])
const loading = ref(false)
const saving = ref(false)
const reorderingHost = ref<ShortcutHost>()
const error = ref('')
const submitted = ref(false)
const editingId = ref<string>()
const showModal = ref(false)
const deletingShortcut = ref<Shortcut>()
const deletingShortcutId = ref<string>()
const deleteDialogOpen = computed({
  get: () => !!deletingShortcut.value,
  set: (open: boolean) => {
    if (!open && !deletingShortcutId.value) {
      deletingShortcut.value = undefined
    }
  },
})
const environmentsByHost = computed(
  () => new Map(environments.value.map((environment) => [environment.host, environment])),
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
const validationErrors = computed<Record<FieldName, string>>(() => {
  const errors = emptyFieldErrors()
  errors.name = form.name ? '' : t('shortcutManagement.validation.nameRequired')
  errors.command = form.command ? '' : t('shortcutManagement.validation.commandRequired')
  errors.host = form.host ? '' : t('shortcutManagement.validation.hostRequired')

  if (!errors.name && form.host && hasDuplicateName()) {
    errors.name = t('shortcutManagement.validation.nameUniquePerHost')
  }

  return errors
})
const fieldErrors = computed<Record<FieldName, string>>(() => {
  if (!submitted.value) {
    return emptyFieldErrors()
  }
  return validationErrors.value
})
const editingShortcutInUse = computed(() => {
  if (!editingId.value) {
    return false
  }
  return shortcutEnvironments.value.some((environment) =>
    environment.shortcuts.some(
      (shortcut) => shortcut.id === editingId.value && shortcut.used_session_count > 0,
    ),
  )
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
    shortcutEnvironments.value = shortcutResponse.environments
    environments.value = environmentResponse.environments
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('shortcutManagement.errors.load')
  } finally {
    loading.value = false
  }
}

function hasDragged(event: DragEndEvent) {
  return (
    event.oldIndex !== undefined &&
    event.newIndex !== undefined &&
    event.oldIndex !== event.newIndex
  )
}

async function handleShortcutReorder(event: DragEndEvent, host: ShortcutHost, shortcuts: Shortcut[]) {
  if (!hasDragged(event)) {
    return
  }
  const currentHost = reorderingHost.value
  if (currentHost === host) {
    return
  }
  const shortcutIds = shortcuts.map((shortcut) => shortcut.id)
  reorderingHost.value = host
  try {
    const response = await reorderShortcuts(host, { shortcut_ids: shortcutIds })
    shortcutEnvironments.value = response.environments
  } catch {
    toast.show({
      title: t('shortcutManagement.errors.reorder'),
      variant: 'error',
    })
    await load()
  } finally {
    reorderingHost.value = undefined
  }
}

function openCreateModal(host?: ShortcutHost) {
  resetForm()
  if (host) {
    form.host = host
  }
  showModal.value = true
}

function edit(shortcut: Shortcut) {
  editingId.value = shortcut.id
  submitted.value = false
  form.name = shortcut.name
  form.command = shortcut.command
  form.host = shortcut.host
  form.description = shortcut.description || ''
  showModal.value = true
}

function resetForm() {
  editingId.value = undefined
  submitted.value = false
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
  if (saving.value || !validate()) {
    return
  }

  saving.value = true
  try {
    const payload = normalizePayload()
    const updating = !!editingId.value
    if (editingId.value) {
      const updated = await updateShortcut(editingId.value, payload)
      replaceShortcut(updated)
    } else {
      await createShortcut(payload)
      await load()
    }
    closeModal()
    toast.show({
      title: t(
        updating ? 'shortcutManagement.success.updated' : 'shortcutManagement.success.created',
      ),
      variant: 'success',
    })
  } catch (err) {
    toast.show({
      title: err instanceof Error ? err.message : t('shortcutManagement.errors.save'),
      variant: 'error',
    })
  } finally {
    saving.value = false
  }
}

function replaceShortcut(updated: Shortcut) {
  for (const environment of shortcutEnvironments.value) {
    const index = environment.shortcuts.findIndex((shortcut) => shortcut.id === updated.id)
    if (index === -1) {
      continue
    }

    if (environment.host === updated.host) {
      environment.shortcuts[index] = updated
    } else {
      environment.shortcuts.splice(index, 1)
      const targetEnvironment = shortcutEnvironments.value.find((item) => item.host === updated.host)
      targetEnvironment?.shortcuts.push(updated)
    }
    return
  }
}

function createSessionFromShortcut(shortcut: Shortcut) {
  emit('createSession', { host: shortcut.host, shortcutId: shortcut.id })
}

function askRemoveShortcut(shortcut: Shortcut) {
  if (shortcut.used_session_count > 0) {
    return
  }
  deletingShortcut.value = shortcut
}

async function confirmRemoveShortcut() {
  if (!deletingShortcut.value || deletingShortcutId.value) {
    return
  }

  const shortcutId = deletingShortcut.value.id
  deletingShortcutId.value = shortcutId
  try {
    await deleteShortcut(shortcutId)
    deletingShortcut.value = undefined
    await load()
    toast.show({ title: t('shortcutManagement.success.deleted'), variant: 'success' })
  } catch (err) {
    toast.show({
      title: err instanceof Error ? err.message : t('shortcutManagement.errors.delete'),
      variant: 'error',
    })
  } finally {
    deletingShortcutId.value = undefined
  }
}

function validate(): boolean {
  submitted.value = true
  return !Object.values(validationErrors.value).some(Boolean)
}

function hasDuplicateName(): boolean {
  const name = form.name.trim()
  const environment = shortcutEnvironments.value.find((item) => item.host === form.host)
  return !!environment?.shortcuts.some(
    (shortcut) => shortcut.id !== editingId.value && shortcut.name === name,
  )
}

function emptyFieldErrors(): Record<FieldName, string> {
  return {
    name: '',
    command: '',
    host: '',
  }
}

function normalizePayload(): CreateShortcutPayload {
  return {
    name: form.name.trim(),
    command: form.command.trim(),
    host: form.host as ShortcutHost,
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
    <div>
      <h2 class="text-lg font-semibold text-slate-950 dark:text-slate-100">
        {{ t('shortcutManagement.title') }}
      </h2>
    </div>

    <p v-if="error" class="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <p v-if="loading" class="inline-flex items-center gap-2 text-sm text-slate-500">
      <Loader2 class="h-4 w-4 animate-spin" />
      {{ t('shortcutManagement.loading') }}
    </p>

    <div class="grid min-h-0 flex-1 content-start gap-4 overflow-auto pr-1">
      <section v-for="group in shortcutEnvironments" :key="group.host" class="grid gap-2.5">
        <div class="flex items-center gap-2 border-b border-slate-200 pb-2 dark:border-slate-800">
          <component :is="hostLogo(group.host)" class="shrink-0" />
          <h3 class="text-sm font-semibold text-slate-950 dark:text-slate-100">
            {{ hostLabel(group.host) }}
          </h3>
          <button
            type="button"
            class="ml-auto inline-flex items-center justify-center gap-1.5 rounded-md border border-blue-200 px-2 py-1 text-sm text-blue-600 transition hover:bg-blue-50 dark:border-blue-900/60 dark:text-blue-400 dark:hover:bg-blue-950/40"
            @click="openCreateModal(group.host)"
          >
            <Plus class="h-4 w-4" />
            {{ t('shortcutManagement.actions.create') }}
          </button>
        </div>

        <VueDraggable
          v-model="group.shortcuts"
          :group="{ name: `shortcuts:${group.host}`, pull: false, put: false }"
          ghost-class="shortcut-card-ghost"
          filter="button"
          :prevent-on-filter="false"
          :disabled="!!reorderingHost"
          class="grid gap-2.5 md:grid-cols-3 xl:grid-cols-4"
          @end="handleShortcutReorder($event, group.host, group.shortcuts)"
        >
          <article
            v-for="shortcut in group.shortcuts"
            :key="shortcut.id"
            class="group relative flex cursor-grab flex-col justify-between border border-slate-200 bg-white/35 p-2.5 pb-12 transition hover:border-blue-400 hover:bg-white/70 active:cursor-grabbing dark:border-slate-800 dark:bg-slate-950 dark:hover:border-blue-500 dark:hover:bg-slate-900/50"
          >
            <div>
              <div class="flex min-w-0 items-center gap-1.5">
                <GripVertical class="h-4 w-4 shrink-0 text-slate-400 dark:text-slate-500" />
                <p class="truncate text-sm font-semibold text-slate-950 dark:text-slate-100">
                  {{ shortcut.name }}
                </p>
              </div>
              <p
                class="mt-1.5 truncate rounded-md border border-slate-300 bg-slate-200/80 px-2 py-1.5 font-mono text-xs text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
                :title="shortcut.command"
              >
                {{ shortcut.command }}
              </p>
            </div>

            <div class="absolute bottom-2.5 right-2.5 flex gap-1.5">
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
                :disabled="shortcut.used_session_count > 0"
                :title="
                  shortcut.used_session_count > 0
                    ? t('shortcutManagement.delete.inUse', {
                        count: shortcut.used_session_count,
                      })
                    : undefined
                "
                @click="askRemoveShortcut(shortcut)"
              >
                {{ t('app.actions.delete') }}
              </button>
            </div>
          </article>
        </VueDraggable>
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
                class="rounded-md border border-slate-300 bg-white/60 px-3 py-2 outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
                :class="fieldErrors.name ? fieldErrorClass : ''"
                :aria-invalid="!!fieldErrors.name"
                :aria-describedby="fieldErrors.name ? 'shortcut-name-error' : undefined"
              />
              <span
                v-if="fieldErrors.name"
                id="shortcut-name-error"
                :class="fieldErrorMessageClass"
              >
                {{ fieldErrors.name }}
              </span>
            </label>
            <label class="grid gap-1.5 text-sm text-slate-700 dark:text-slate-300">
              {{ t('shortcutManagement.fields.command') }}
              <input
                v-model.trim="form.command"
                :disabled="editingShortcutInUse"
                class="rounded-md border border-slate-300 bg-white/60 px-3 py-2 font-mono text-xs outline-none transition focus:border-blue-500 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
                :class="fieldErrors.command ? fieldErrorClass : ''"
                :aria-invalid="!!fieldErrors.command"
                :aria-describedby="fieldErrors.command ? 'shortcut-command-error' : undefined"
                :title="editingShortcutInUse ? t('shortcutManagement.fields.commandLocked') : undefined"
              />
              <span v-if="editingShortcutInUse" class="text-xs text-slate-500 dark:text-slate-400">
                {{ t('shortcutManagement.fields.commandLocked') }}
              </span>
              <span
                v-if="fieldErrors.command"
                id="shortcut-command-error"
                :class="fieldErrorMessageClass"
              >
                {{ fieldErrors.command }}
              </span>
            </label>
            <label class="grid gap-1.5 text-sm text-slate-700 dark:text-slate-300">
              {{ t('shortcutManagement.fields.host') }}
              <SelectRoot v-model="form.host">
                <SelectTrigger
                  class="flex items-center justify-between rounded-md border border-slate-300 bg-white/60 px-3 py-2 text-left outline-none transition focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-blue-500"
                  :class="fieldErrors.host ? fieldErrorClass : ''"
                  :aria-invalid="!!fieldErrors.host"
                  :aria-describedby="fieldErrors.host ? 'shortcut-host-error' : undefined"
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
              <span
                v-if="fieldErrors.host"
                id="shortcut-host-error"
                :class="fieldErrorMessageClass"
              >
                {{ fieldErrors.host }}
              </span>
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
                  :disabled="saving"
                  class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
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
            <AlertDialogCancel
              :disabled="!!deletingShortcutId"
              class="rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              {{ t('app.actions.cancel') }}
            </AlertDialogCancel>
            <button
              type="button"
              :disabled="!!deletingShortcutId"
              class="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-white transition hover:bg-red-700 disabled:cursor-wait disabled:opacity-60"
              @click="confirmRemoveShortcut"
            >
              <Loader2 v-if="deletingShortcutId" class="h-4 w-4 animate-spin" />
              {{ t('app.actions.delete') }}
            </button>
          </div>
        </AlertDialogContent>
      </AlertDialogPortal>
    </AlertDialogRoot>
  </section>
</template>

<style scoped>
:deep(.shortcut-card-ghost) {
  border-radius: 0.5rem;
  border-color: rgb(96 165 250 / 0.55);
  background-color: rgb(219 234 254 / 0.75);
}

:global(.dark) :deep(.shortcut-card-ghost) {
  border-color: rgb(59 130 246 / 0.6);
  background-color: rgb(30 58 138 / 0.55);
}
</style>
