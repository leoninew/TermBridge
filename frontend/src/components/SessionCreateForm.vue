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
import { FolderOpen, Plus } from '@lucide/vue'
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { listShortcuts } from '../api/sessions'
import type { CreateSessionPayload, Shortcut } from '../types/sessions'
import WorkspaceBrowser from './WorkspaceBrowser.vue'

const { t } = useI18n()
const emit = defineEmits<{
  create: [payload: CreateSessionPayload]
  cancel: []
}>()

const shortcuts = ref<Shortcut[]>([])
const shortcutError = ref('')
const form = reactive<CreateSessionPayload>({
  name: '',
  workspace: '',
  shortcut_id: '',
})
const submitting = ref(false)
const showWorkspaceBrowser = ref(false)

onMounted(loadShortcuts)

async function loadShortcuts() {
  try {
    const response = await listShortcuts()
    shortcuts.value = response.shortcuts
    form.shortcut_id = shortcuts.value[0]?.id || ''
  } catch (err) {
    shortcutError.value =
      err instanceof Error ? err.message : t('session.create.loadShortcutsError')
  }
}

function selectWorkspace(path: string) {
  form.workspace = path
  fillNameFromWorkspace()
}

function fillNameFromWorkspace() {
  if (form.name.trim()) {
    return
  }
  const workspaceName = form.workspace
    .trim()
    .replace(/[\\/]+$/, '')
    .split(/[\\/]/)
    .pop()
  if (workspaceName) {
    form.name = workspaceName
  }
}

async function submit() {
  submitting.value = true
  emit('create', {
    name: form.name,
    workspace: form.workspace,
    shortcut_id: form.shortcut_id,
  })
  submitting.value = false
}
</script>

<template>
  <form class="grid gap-5" @submit.prevent="submit">
    <div>
      <h2 class="text-lg font-semibold text-slate-950">{{ t('session.create.title') }}</h2>
      <p class="mt-1 text-sm text-slate-500">{{ t('session.create.description') }}</p>
    </div>

    <p v-if="shortcutError" class="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
      {{ shortcutError }}
    </p>

    <div class="grid gap-2 text-sm text-slate-700">
      <span>{{ t('session.create.workspace') }}</span>
      <div class="flex gap-2">
        <input
          v-model.trim="form.workspace"
          required
          class="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
          :placeholder="t('session.create.workspacePlaceholder')"
          @change="fillNameFromWorkspace"
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
        class="rounded-xl border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
        :placeholder="t('session.create.namePlaceholder')"
      />
    </label>

    <label class="grid gap-2 text-sm text-slate-700">
      {{ t('session.create.shortcut') }}
      <SelectRoot v-model="form.shortcut_id" required>
        <SelectTrigger
          class="flex items-center justify-between rounded-xl border border-slate-300 bg-white px-3 py-2 text-left outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent
          class="z-50 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
        >
          <SelectViewport class="p-1">
            <SelectItem
              v-for="shortcut in shortcuts"
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
        class="rounded-xl border border-slate-300 px-4 py-2 text-slate-700 transition hover:bg-slate-50"
        @click="emit('cancel')"
      >
        {{ t('app.actions.cancel') }}
      </button>
      <button
        type="submit"
        :disabled="submitting || !form.shortcut_id"
        class="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-60"
      >
        <Plus class="h-4 w-4" />
        {{ t('session.create.submit') }}
      </button>
    </div>
  </form>
</template>
