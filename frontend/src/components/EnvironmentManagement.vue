<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Monitor, RefreshCw, Terminal } from '@lucide/vue'
import { ToastProvider, ToastRoot, ToastTitle, ToastViewport } from 'reka-ui'
import { useI18n } from 'vue-i18n'
import {
  checkLinux,
  checkTmux,
  checkTtyd,
  checkWindowsCygwin,
  checkWindowsWsl,
  getTerminalSettings,
  getWindowsCygwinSettings,
  updateTerminalSettings,
  updateWindowsCygwinSettings,
} from '../api/sessions'
import type {
  LinuxCheckResponse,
  RuntimeCheckResponse,
  TerminalSettings,
  TmuxAvailabilityResponse,
  WindowsCygwinCheckResponse,
  WindowsCygwinSettings,
  WindowsWslCheckResponse,
} from '../types/sessions'

const { t } = useI18n()
type EnvironmentTab = 'windows_cygwin' | 'windows_wsl' | 'linux'

const activeTab = ref<EnvironmentTab>('windows_cygwin')
const ttydSettings = ref<TerminalSettings>({ ttyd_mode: 'auto', ttyd_path: '' })
const windowsCygwinSettings = ref<WindowsCygwinSettings>({ bash_path: '', tmux_path: '' })
const ttydStatus = ref<RuntimeCheckResponse>()
const tmuxPath = ref('')
const tmuxStatus = ref<TmuxAvailabilityResponse>()
const windowsCygwinStatus = ref<WindowsCygwinCheckResponse>()
const windowsWslStatus = ref<WindowsWslCheckResponse>()
const linuxStatus = ref<LinuxCheckResponse>()
const loading = ref(false)
const checking = ref('')
const error = ref('')
const toastMessage = ref('')
const toastOpen = ref(false)
const checkedTabs = ref(new Set<EnvironmentTab>())

const tabs = computed(() => [
  {
    id: 'windows_cygwin' as const,
    label: t('environmentManagement.tabs.windowsCygwin'),
    icon: Terminal,
  },
  {
    id: 'windows_wsl' as const,
    label: t('environmentManagement.tabs.windowsWsl'),
    icon: Terminal,
  },
  { id: 'linux' as const, label: t('environmentManagement.tabs.linux'), icon: Monitor },
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
    const [ttyd, windowsCygwin] = await Promise.all([
      getTerminalSettings(),
      getWindowsCygwinSettings(),
    ])
    ttydSettings.value = { ...ttyd, ttyd_path: ttyd.ttyd_path || '' }
    windowsCygwinSettings.value = {
      ...windowsCygwin,
      bash_path: windowsCygwin.bash_path || '',
      tmux_path: windowsCygwin.tmux_path || '',
    }
    tmuxPath.value = windowsCygwin.tmux_path || ''
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
    if (tab === 'windows_cygwin') {
      await refreshWindowsCygwin(false)
    } else if (tab === 'windows_wsl') {
      windowsWslStatus.value = await checkWindowsWsl()
    } else {
      linuxStatus.value = await checkLinux()
    }
    checkedTabs.value.add(tab)
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    checking.value = ''
  }
}

async function refreshWindowsCygwin(setChecking = true) {
  if (setChecking) {
    checking.value = 'windows_cygwin'
    error.value = ''
  }
  try {
    const path = windowsCygwinSettings.value.bash_path?.trim() || undefined
    const status = await checkWindowsCygwin(path)
    windowsCygwinStatus.value = status
    if (status.bash.available && status.bash.path) {
      windowsCygwinSettings.value = await updateWindowsCygwinSettings({
        ...windowsCygwinSettings.value,
        bash_path: status.bash.path,
      })
      showToast(t('environmentManagement.windowsCygwin.saved'))
    }
    if (status.tmux?.available && status.tmux.path) {
      tmuxPath.value = status.tmux.path
      tmuxStatus.value = status.tmux
      windowsCygwinSettings.value = await updateWindowsCygwinSettings({
        ...windowsCygwinSettings.value,
        tmux_path: status.tmux.path,
      })
    }
    checkedTabs.value.add('windows_cygwin')
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    if (setChecking) {
      checking.value = ''
    }
  }
}

async function refreshTmux() {
  const bashPath = windowsCygwinSettings.value.bash_path?.trim()
  if (!bashPath) {
    await refreshWindowsCygwin()
    return
  }

  checking.value = 'tmux'
  error.value = ''
  try {
    const status = await checkTmux({ cygwin_bash_path: bashPath })
    tmuxStatus.value = status
    if (status.available && status.path) {
      tmuxPath.value = status.path
      windowsCygwinSettings.value = await updateWindowsCygwinSettings({
        ...windowsCygwinSettings.value,
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
        class="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 transition hover:bg-white/70 hover:text-slate-950"
        :class="
          activeTab === tab.id
            ? 'bg-white text-blue-700 shadow-sm ring-1 ring-slate-200'
            : 'text-slate-600'
        "
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
      v-if="activeTab === 'windows_cygwin'"
      class="grid gap-4 rounded-xl border border-slate-200 p-4"
    >
      <div>
        <h3 class="text-lg font-semibold text-slate-950">
          {{ t('environmentManagement.windowsCygwin.title') }}
        </h3>
      </div>

      <div class="grid gap-2">
        <label class="grid gap-2 text-sm text-slate-700">
          {{ t('environmentManagement.windowsCygwin.bashPath') }}
          <div class="flex gap-2">
            <input
              v-model.trim="windowsCygwinSettings.bash_path"
              class="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
              placeholder="bash"
            />
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              :disabled="checking === 'windows_cygwin'"
              @click="() => refreshWindowsCygwin()"
            >
              <RefreshCw
                class="h-4 w-4"
                :class="checking === 'windows_cygwin' ? 'animate-spin' : ''"
              />
              {{ t('environmentManagement.actions.check') }}
            </button>
          </div>
        </label>
        <p
          v-if="windowsCygwinStatus?.bash.available && windowsCygwinStatus.bash.version"
          class="text-sm text-slate-500"
        >
          {{ windowsCygwinStatus.bash.version }}
        </p>
        <p
          v-else-if="windowsCygwinStatus && !windowsCygwinStatus.bash.available"
          class="text-sm text-red-600"
        >
          {{ windowsCygwinStatus.bash.reason }}
        </p>
      </div>

      <div class="grid gap-2">
        <label class="grid gap-2 text-sm text-slate-700">
          {{ t('environmentManagement.windowsCygwin.tmuxPath') }}
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
      v-else-if="activeTab === 'windows_wsl'"
      class="grid gap-3 rounded-xl border border-slate-200 p-4"
    >
      <div>
        <h3 class="text-lg font-semibold text-slate-950">
          {{ t('environmentManagement.windowsWsl.title') }}
        </h3>
      </div>
      <div class="grid gap-1 text-sm">
        <p
          v-if="windowsWslStatus?.wsl.available && windowsWslStatus.wsl.version"
          class="text-slate-500"
        >
          {{ windowsWslStatus.wsl.version }}
        </p>
        <p v-else-if="windowsWslStatus && !windowsWslStatus.wsl.available" class="text-red-600">
          {{ windowsWslStatus.wsl.reason }}
        </p>
        <p
          v-if="windowsWslStatus?.tmux?.available && windowsWslStatus.tmux.version"
          class="text-slate-500"
        >
          {{ windowsWslStatus.tmux.version }}
        </p>
        <p
          v-else-if="windowsWslStatus?.tmux && !windowsWslStatus.tmux.available"
          class="text-red-600"
        >
          {{ windowsWslStatus.tmux.reason }}
        </p>
      </div>
    </section>

    <section v-else class="grid gap-3 rounded-xl border border-slate-200 p-4">
      <div>
        <h3 class="text-lg font-semibold text-slate-950">
          {{ t('environmentManagement.linux.title') }}
        </h3>
      </div>
      <div class="grid gap-1 text-sm">
        <p v-if="linuxStatus?.host.available" class="text-slate-500">
          {{ linuxStatus.host.path }}
        </p>
        <p v-else-if="linuxStatus" class="text-red-600">
          {{ linuxStatus.host.reason }}
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
