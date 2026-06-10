<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Monitor, RefreshCw, Terminal } from '@lucide/vue'
import { ToastProvider, ToastRoot, ToastTitle, ToastViewport } from 'reka-ui'
import { useI18n } from 'vue-i18n'
import {
  checkCygwin,
  checkTmux,
  checkTtyd,
  checkWindows,
  checkWsl,
  getCygwinSettings,
  getTerminalSettings,
  updateCygwinSettings,
  updateTerminalSettings,
} from '../api/sessions'
import type {
  CygwinCheckResponse,
  CygwinSettings,
  RuntimeCheckResponse,
  TmuxAvailabilityResponse,
  TerminalSettings,
  WindowsCheckResponse,
  WslCheckResponse,
} from '../types/sessions'

const { t } = useI18n()
type EnvironmentTab = 'windows' | 'cygwin' | 'wsl'

const activeTab = ref<EnvironmentTab>('cygwin')
const ttydSettings = ref<TerminalSettings>({ ttyd_mode: 'auto', ttyd_path: '' })
const cygwinSettings = ref<CygwinSettings>({ bash_path: '', tmux_path: '' })
const ttydStatus = ref<RuntimeCheckResponse>()
const tmuxPath = ref('')
const tmuxStatus = ref<TmuxAvailabilityResponse>()
const cygwinStatus = ref<CygwinCheckResponse>()
const windowsStatus = ref<WindowsCheckResponse>()
const wslStatus = ref<WslCheckResponse>()
const loading = ref(false)
const checking = ref('')
const error = ref('')
const toastMessage = ref('')
const toastOpen = ref(false)
const checkedTabs = ref(new Set<EnvironmentTab>())

const tabs = computed(() => [
  { id: 'cygwin' as const, label: t('environmentManagement.tabs.cygwin'), icon: Terminal },
  { id: 'windows' as const, label: t('environmentManagement.tabs.windows'), icon: Monitor, disabled: true },
  { id: 'wsl' as const, label: t('environmentManagement.tabs.wsl'), icon: Terminal, disabled: true },
])

onMounted(async () => {
  await loadSettings()
  await Promise.all([refreshTtyd(), refreshActiveTab()])
})

watch(activeTab, () => {
  void refreshActiveTab()
})

async function loadSettings() {
  loading.value = true
  error.value = ''
  try {
    const [ttyd, cygwin] = await Promise.all([getTerminalSettings(), getCygwinSettings()])
    ttydSettings.value = { ...ttyd, ttyd_path: ttyd.ttyd_path || '' }
    cygwinSettings.value = {
      ...cygwin,
      bash_path: cygwin.bash_path || '',
      tmux_path: cygwin.tmux_path || '',
    }
    tmuxPath.value = cygwin.tmux_path || ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.load')
  } finally {
    loading.value = false
  }
}

async function refreshTtyd() {
  checking.value = 'ttyd'
  error.value = ''
  try {
    const path = ttydSettings.value.ttyd_path?.trim() || undefined
    const status = await checkTtyd(path)
    ttydStatus.value = status
    if (status.available && status.path) {
      ttydSettings.value = await updateTerminalSettings({
        ttyd_mode: 'explicit',
        ttyd_path: status.path,
      })
      showToast(t('environmentManagement.ttyd.saved'))
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    checking.value = ''
  }
}

async function refreshActiveTab() {
  if (checkedTabs.value.has(activeTab.value)) {
    return
  }
  await refreshTab(activeTab.value)
}

async function refreshTab(tab: EnvironmentTab = activeTab.value) {
  checking.value = tab
  error.value = ''
  try {
    if (tab === 'windows') {
      windowsStatus.value = await checkWindows()
    } else if (tab === 'cygwin') {
      await refreshCygwin(false)
    } else {
      wslStatus.value = await checkWsl()
    }
    checkedTabs.value.add(tab)
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    checking.value = ''
  }
}

async function refreshCygwin(setChecking = true) {
  if (setChecking) {
    checking.value = 'cygwin'
    error.value = ''
  }
  try {
    const path = cygwinSettings.value.bash_path?.trim() || undefined
    const status = await checkCygwin(path)
    cygwinStatus.value = status
    if (status.bash.available && status.bash.path) {
      cygwinSettings.value = await updateCygwinSettings({
        ...cygwinSettings.value,
        bash_path: status.bash.path,
      })
      showToast(t('environmentManagement.cygwin.saved'))
    }
    if (status.tmux?.available && status.tmux.path) {
      tmuxPath.value = status.tmux.path
      tmuxStatus.value = status.tmux
      cygwinSettings.value = await updateCygwinSettings({
        ...cygwinSettings.value,
        tmux_path: status.tmux.path,
      })
    }
    checkedTabs.value.add('cygwin')
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    if (setChecking) {
      checking.value = ''
    }
  }
}

async function refreshTmux() {
  const bashPath = cygwinSettings.value.bash_path?.trim()
  if (!bashPath) {
    await refreshCygwin()
    return
  }

  checking.value = 'tmux'
  error.value = ''
  try {
    const status = await checkTmux({ cygwin_bash_path: bashPath })
    tmuxStatus.value = status
    if (status.available && status.path) {
      tmuxPath.value = status.path
      cygwinSettings.value = await updateCygwinSettings({
        ...cygwinSettings.value,
        tmux_path: status.path,
      })
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    checking.value = ''
  }
}

async function showToast(message: string) {
  toastOpen.value = false
  toastMessage.value = message
  await nextTick()
  toastOpen.value = true
}
</script>

<template>
  <section
    class="grid min-h-full content-start gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl shadow-blue-900/5"
  >
    <div>
      <h2 class="text-lg font-semibold text-slate-950">{{ t('environmentManagement.title') }}</h2>
    </div>

    <p v-if="error" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <section class="rounded-xl border border-slate-200 p-4">
      <div>
        <h3 class="text-lg font-semibold text-slate-950">
          {{ t('environmentManagement.ttyd.title') }}
        </h3>
      </div>

      <div class="mt-4 grid gap-2">
        <label class="grid gap-2 text-sm text-slate-700">
          {{ t('environmentManagement.ttyd.path') }}
          <div class="flex gap-2">
            <input
              v-model.trim="ttydSettings.ttyd_path"
              class="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
              placeholder="ttyd"
            />
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              :disabled="checking === 'ttyd'"
              @click="refreshTtyd"
            >
              <RefreshCw class="h-4 w-4" :class="checking === 'ttyd' ? 'animate-spin' : ''" />
              {{ t('environmentManagement.actions.check') }}
            </button>
          </div>
        </label>
        <p v-if="ttydStatus?.available && ttydStatus.version" class="text-sm text-slate-500">
          {{ ttydStatus.version }}
        </p>
        <p v-else-if="ttydStatus && !ttydStatus.available" class="text-sm text-red-600">
          {{ ttydStatus.reason }}
        </p>
      </div>
    </section>

    <div class="flex flex-wrap gap-2 rounded-xl bg-slate-100 p-1">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        class="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 transition hover:bg-white/70 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-transparent disabled:hover:text-slate-600"
        :class="
          activeTab === tab.id
            ? 'bg-white text-blue-700 shadow-sm ring-1 ring-slate-200'
            : 'text-slate-600'
        "
        :disabled="tab.disabled"
        @click="activeTab = tab.id"
      >
        <component
          :is="tab.icon"
          class="h-4 w-4"
          :class="activeTab === tab.id ? 'text-blue-600' : 'text-slate-400'"
        />
        {{ tab.label }}
      </button>
    </div>

    <section
      v-if="activeTab === 'cygwin'"
      class="grid gap-4 rounded-xl border border-slate-200 p-4"
    >
      <div>
        <h3 class="text-lg font-semibold text-slate-950">
          {{ t('environmentManagement.cygwin.title') }}
        </h3>
      </div>

      <div class="grid gap-2">
        <label class="grid gap-2 text-sm text-slate-700">
          {{ t('environmentManagement.cygwin.bashPath') }}
          <div class="flex gap-2">
            <input
              v-model.trim="cygwinSettings.bash_path"
              class="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
              placeholder="bash"
            />
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              :disabled="checking === 'cygwin'"
              @click="() => refreshCygwin()"
            >
              <RefreshCw class="h-4 w-4" :class="checking === 'cygwin' ? 'animate-spin' : ''" />
              {{ t('environmentManagement.actions.check') }}
            </button>
          </div>
        </label>
        <p
          v-if="cygwinStatus?.bash.available && cygwinStatus.bash.version"
          class="text-sm text-slate-500"
        >
          {{ cygwinStatus.bash.version }}
        </p>
        <p v-else-if="cygwinStatus && !cygwinStatus.bash.available" class="text-sm text-red-600">
          {{ cygwinStatus.bash.reason }}
        </p>
      </div>

      <div class="grid gap-2">
        <label class="grid gap-2 text-sm text-slate-700">
          {{ t('environmentManagement.cygwin.tmuxPath') }}
          <div class="flex gap-2">
            <input
              v-model.trim="tmuxPath"
              class="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
              placeholder="tmux"
              readonly
            />
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              :disabled="checking === 'tmux'"
              @click="refreshTmux"
            >
              <RefreshCw class="h-4 w-4" :class="checking === 'tmux' ? 'animate-spin' : ''" />
              {{ t('environmentManagement.actions.check') }}
            </button>
          </div>
        </label>
        <p v-if="tmuxStatus?.available && tmuxStatus.version" class="text-sm text-slate-500">
          {{ tmuxStatus.version }}
        </p>
        <p v-else-if="tmuxStatus && !tmuxStatus.available" class="text-sm text-red-600">
          {{ tmuxStatus.reason }}
        </p>
      </div>
    </section>

    <section
      v-else-if="activeTab === 'windows'"
      class="grid gap-3 rounded-xl border border-slate-200 p-4"
    >
      <div>
        <h3 class="text-lg font-semibold text-slate-950">
          {{ t('environmentManagement.windows.title') }}
        </h3>
      </div>
      <div class="grid gap-1 text-sm">
        <p v-if="windowsStatus?.host.available && windowsStatus.host.version" class="text-slate-500">
          {{ windowsStatus.host.version }}
        </p>
        <p v-else-if="windowsStatus && !windowsStatus.host.available" class="text-red-600">
          {{ windowsStatus.host.reason }}
        </p>
      </div>
    </section>

    <section v-else class="grid gap-3 rounded-xl border border-slate-200 p-4">
      <div>
        <h3 class="text-lg font-semibold text-slate-950">
          {{ t('environmentManagement.wsl.title') }}
        </h3>
      </div>
      <div class="grid gap-1 text-sm">
        <p v-if="wslStatus?.wsl.available && wslStatus.wsl.version" class="text-slate-500">
          {{ wslStatus.wsl.version }}
        </p>
        <p v-else-if="wslStatus && !wslStatus.wsl.available" class="text-red-600">
          {{ wslStatus.wsl.reason }}
        </p>
      </div>
    </section>

    <ToastProvider>
      <ToastRoot
        v-model:open="toastOpen"
        class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-xl shadow-blue-900/10"
      >
        <ToastTitle>{{ toastMessage }}</ToastTitle>
      </ToastRoot>
      <ToastViewport class="fixed right-4 top-4 z-50 grid w-80 max-w-[calc(100vw-2rem)] gap-2" />
    </ToastProvider>
  </section>
</template>
