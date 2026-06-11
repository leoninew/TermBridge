<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Loader2, RefreshCw } from '@lucide/vue'
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { useI18n } from 'vue-i18n'
import CygwinLogo from './CygwinLogo.vue'
import LinuxLogo from './LinuxLogo.vue'
import WslLogo from './WslLogo.vue'
import { useToastStore } from '../stores/toast'
import {
  checkLinux,
  checkTtyd,
  checkWindowsCygwin,
  checkWindowsWsl,
  getTerminalSettings,
  getWindowsCygwinSettings,
  getWindowsWslSettings,
  listEnvironments,
  updateTerminalSettings,
} from '../api/sessions'
import type {
  EnvironmentSummary,
  LinuxCheckResponse,
  RuntimeCheckResponse,
  TerminalSettings,
  WindowsCygwinCheckResponse,
  WindowsCygwinSettings,
  WindowsWslCheckResponse,
  WindowsWslSettings,
} from '../types/sessions'

const { t } = useI18n()
const route = useRoute()
const toast = useToastStore()
const emit = defineEmits<{
  environmentsUpdated: [environments: EnvironmentSummary[]]
}>()
type EnvironmentTab = 'windows_cygwin' | 'windows_wsl' | 'linux'

const activeTab = ref<EnvironmentTab>('windows_cygwin')
const ttydSettings = ref<TerminalSettings>({ ttyd_mode: 'auto', ttyd_path: '' })
const environments = ref<EnvironmentSummary[]>([])
const windowsCygwinSettings = ref<WindowsCygwinSettings>({
  readiness: 'not_ready',
  bash_path: '',
  tmux_path: '',
})
const windowsWslSettings = ref<WindowsWslSettings>({ readiness: 'not_ready' })
const ttydStatus = ref<RuntimeCheckResponse>()
const tmuxPath = ref('')
const windowsCygwinStatus = ref<WindowsCygwinCheckResponse>()
const windowsWslStatus = ref<WindowsWslCheckResponse>()
const linuxStatus = ref<LinuxCheckResponse>()
const loading = ref(false)
const checking = ref('')
const error = ref('')
const environmentsByHost = computed(
  () => new Map(environments.value.map((environment) => [environment.host, environment])),
)

const tabs = computed(() => [
  {
    id: 'windows_cygwin' as const,
    label: t('environmentManagement.tabs.windowsCygwin'),
    icon: CygwinLogo,
  },
  {
    id: 'windows_wsl' as const,
    label: t('environmentManagement.tabs.windowsWsl'),
    icon: WslLogo,
  },
  { id: 'linux' as const, label: t('environmentManagement.tabs.linux'), icon: LinuxLogo },
])

function initialTab(): EnvironmentTab {
  const tab = route.query.tab
  return tab === 'windows_cygwin' || tab === 'windows_wsl' || tab === 'linux'
    ? tab
    : 'windows_cygwin'
}

onMounted(async () => {
  activeTab.value = initialTab()
  await loadSettings()
  await refreshTtyd()
  await refreshTab()
})

async function loadSettings() {
  loading.value = true
  error.value = ''
  try {
    const [ttyd, environmentResponse] = await Promise.all([
      getTerminalSettings(),
      listEnvironments(),
    ])
    ttydSettings.value = { ...ttyd, ttyd_path: ttyd.ttyd_path || '' }
    environments.value = environmentResponse.environments
    await loadTabSettings(activeTab.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.load')
  } finally {
    loading.value = false
  }
}

async function loadTabSettings(tab: EnvironmentTab) {
  if (tab === 'windows_cygwin') {
    const windowsCygwin = await getWindowsCygwinSettings()
    windowsCygwinSettings.value = {
      ...windowsCygwin,
      bash_path: windowsCygwin.bash_path || '',
      tmux_path: windowsCygwin.tmux_path || '',
    }
    tmuxPath.value = windowsCygwin.tmux_path || ''
  } else if (tab === 'windows_wsl') {
    windowsWslSettings.value = await getWindowsWslSettings()
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
      const previousPath = ttydSettings.value.ttyd_path || ''
      ttydSettings.value = await updateTerminalSettings({
        ttyd_mode: 'explicit',
        ttyd_path: status.path,
      })
      if (status.path !== previousPath) {
        toast.show({ title: t('environmentManagement.ttyd.saved'), variant: 'success' })
      }
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    checking.value = ''
  }
}

async function refreshTab(tab: EnvironmentTab = activeTab.value) {
  checking.value = tab
  error.value = ''
  try {
    if (tab === 'windows_cygwin') {
      await refreshWindowsCygwin(false)
    } else if (tab === 'windows_wsl') {
      const status = await checkWindowsWsl()
      windowsWslStatus.value = status
      if (status.wsl.available && status.wsl.path) {
        windowsWslSettings.value.wsl_path = status.wsl.path
        windowsWslSettings.value.wsl_version = status.wsl.version
      }
      if (status.tmux?.available && status.tmux.path) {
        windowsWslSettings.value.tmux_path = status.tmux.path
        windowsWslSettings.value.tmux_version = status.tmux.version
      }
      toast.show({ title: t('environmentManagement.windowsWsl.checked'), variant: 'success' })
    } else {
      linuxStatus.value = await checkLinux()
      toast.show({ title: t('environmentManagement.linux.checked'), variant: 'success' })
    }
    const updatedEnvironments = await refreshEnvironmentSummary()
    emit('environmentsUpdated', updatedEnvironments)
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    checking.value = ''
  }
}

async function refreshEnvironmentSummary(): Promise<EnvironmentSummary[]> {
  environments.value = (await listEnvironments()).environments
  return environments.value
}

async function updateActiveTab(tab: string | number) {
  const nextTab = tab as EnvironmentTab
  if (activeTab.value === nextTab) {
    return
  }
  activeTab.value = nextTab
  await refreshTab(nextTab)
}

async function refreshWindowsCygwin(setChecking = true) {
  if (setChecking) {
    checking.value = 'windows_cygwin'
    error.value = ''
  }
  try {
    const path = windowsCygwinSettings.value.bash_path?.trim() || undefined
    const previousBashPath = windowsCygwinSettings.value.bash_path || ''
    const previousTmuxPath = tmuxPath.value || ''
    const status = await checkWindowsCygwin(path)
    windowsCygwinStatus.value = status
    if (
      (status.bash.available && status.bash.path && status.bash.path !== previousBashPath) ||
      (status.tmux?.available && status.tmux.path && status.tmux.path !== previousTmuxPath)
    ) {
      toast.show({ title: t('environmentManagement.windowsCygwin.saved'), variant: 'success' })
    }
    if (status.bash.available && status.bash.path) {
      windowsCygwinSettings.value.bash_path = status.bash.path
    }
    if (status.tmux?.available && status.tmux.path) {
      windowsCygwinSettings.value.tmux_path = status.tmux.path
      tmuxPath.value = status.tmux.path
    }
    if (setChecking) {
      const updatedEnvironments = await refreshEnvironmentSummary()
      emit('environmentsUpdated', updatedEnvironments)
    }
  } catch (err) {
    if (!setChecking) {
      throw err
    }
    error.value = err instanceof Error ? err.message : t('environmentManagement.errors.check')
  } finally {
    if (setChecking) {
      checking.value = ''
    }
  }
}

function environmentSummary(host: EnvironmentTab): EnvironmentSummary | undefined {
  return environmentsByHost.value.get(host)
}

function readinessLabel(host: EnvironmentTab): string {
  return environmentSummary(host)?.readiness === 'ready'
    ? t('environmentManagement.readiness.ready')
    : t('environmentManagement.readiness.notReady')
}
</script>

<template>
  <section
    class="grid min-h-full content-start gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl shadow-blue-900/5"
  >
    <div>
      <h2 class="text-lg font-semibold text-slate-950">{{ t('environmentManagement.title') }}</h2>
    </div>

    <p v-if="loading" class="inline-flex items-center gap-2 text-sm text-slate-500">
      <Loader2 class="h-4 w-4 animate-spin" />
      {{ t('environmentManagement.loading') }}
    </p>
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

    <TabsRoot :model-value="activeTab" class="grid gap-4" @update:model-value="updateActiveTab">
      <TabsList class="flex flex-wrap gap-4 border-b border-slate-200">
        <TabsTrigger
          v-for="tab in tabs"
          :key="tab.id"
          :value="tab.id"
          class="-mb-px inline-flex items-center gap-2 border-b-2 border-transparent px-1 py-2 text-sm text-slate-600 transition hover:text-slate-950 data-[state=active]:border-blue-600 data-[state=active]:text-blue-700"
        >
          <component
            :is="tab.icon"
            class="h-4 w-4 text-slate-400"
            :class="activeTab === tab.id ? 'text-blue-600' : 'text-slate-400'"
          />
          {{ tab.label }}
          <span
            class="rounded-full px-2 py-0.5 text-sm"
            :class="
              environmentSummary(tab.id)?.readiness === 'ready'
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-slate-200 text-slate-600'
            "
          >
            {{ readinessLabel(tab.id) }}
          </span>
        </TabsTrigger>
      </TabsList>

      <TabsContent value="windows_cygwin" class="grid gap-4 rounded-xl border border-slate-200 p-4">
        <div class="flex items-start justify-between gap-3">
          <h3 class="text-lg font-semibold text-slate-950">
            {{ t('environmentManagement.windowsCygwin.title') }}
          </h3>
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

        <div class="grid gap-2">
          <label class="grid gap-2 text-sm text-slate-700">
            {{ t('environmentManagement.windowsCygwin.bashPath') }}
            <input
              v-model.trim="windowsCygwinSettings.bash_path"
              class="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
              placeholder="bash"
            />
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
            <input
              v-model.trim="tmuxPath"
              class="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
              placeholder="tmux"
              readonly
            />
          </label>
          <p
            v-if="windowsCygwinStatus?.tmux?.available && windowsCygwinStatus.tmux.version"
            class="text-sm text-slate-500"
          >
            {{ windowsCygwinStatus.tmux.version }}
          </p>
          <p
            v-else-if="windowsCygwinStatus?.tmux && !windowsCygwinStatus.tmux.available"
            class="text-sm text-red-600"
          >
            {{ windowsCygwinStatus.tmux.reason }}
          </p>
        </div>
      </TabsContent>

      <TabsContent value="windows_wsl" class="grid gap-4 rounded-xl border border-slate-200 p-4">
        <div class="flex items-start justify-between gap-3">
          <h3 class="text-lg font-semibold text-slate-950">
            {{ t('environmentManagement.windowsWsl.title') }}
          </h3>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            :disabled="checking === 'windows_wsl'"
            @click="refreshTab('windows_wsl')"
          >
            <RefreshCw class="h-4 w-4" :class="checking === 'windows_wsl' ? 'animate-spin' : ''" />
            {{ t('environmentManagement.actions.check') }}
          </button>
        </div>

        <div class="grid gap-2">
          <label class="grid gap-2 text-sm text-slate-700">
            {{ t('environmentManagement.windowsWsl.wslPath') }}
            <input
              :value="windowsWslSettings.wsl_path || ''"
              class="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
              placeholder="wsl"
              readonly
            />
          </label>
          <p
            v-if="windowsWslStatus?.wsl.available && windowsWslStatus.wsl.version"
            class="text-sm text-slate-500"
          >
            {{ windowsWslStatus.wsl.version }}
          </p>
          <p v-else-if="windowsWslSettings.wsl_version" class="text-sm text-slate-500">
            {{ windowsWslSettings.wsl_version }}
          </p>
          <p
            v-else-if="windowsWslStatus && !windowsWslStatus.wsl.available"
            class="text-sm text-red-600"
          >
            {{ windowsWslStatus.wsl.reason }}
          </p>
        </div>

        <div class="grid gap-2">
          <label class="grid gap-2 text-sm text-slate-700">
            {{ t('environmentManagement.windowsWsl.tmuxPath') }}
            <input
              :value="windowsWslSettings.tmux_path || ''"
              class="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
              placeholder="tmux"
              readonly
            />
          </label>
          <p
            v-if="windowsWslStatus?.tmux?.available && windowsWslStatus.tmux.version"
            class="text-sm text-slate-500"
          >
            {{ windowsWslStatus.tmux.version }}
          </p>
          <p v-else-if="windowsWslSettings.tmux_version" class="text-sm text-slate-500">
            {{ windowsWslSettings.tmux_version }}
          </p>
          <p
            v-else-if="windowsWslStatus?.tmux && !windowsWslStatus.tmux.available"
            class="text-sm text-red-600"
          >
            {{ windowsWslStatus.tmux.reason }}
          </p>
        </div>
      </TabsContent>

      <TabsContent value="linux" class="grid gap-3 rounded-xl border border-slate-200 p-4">
        <div class="flex items-start justify-between gap-3">
          <h3 class="text-lg font-semibold text-slate-950">
            {{ t('environmentManagement.linux.title') }}
          </h3>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            :disabled="checking === 'linux'"
            @click="refreshTab('linux')"
          >
            <RefreshCw class="h-4 w-4" :class="checking === 'linux' ? 'animate-spin' : ''" />
            {{ t('environmentManagement.actions.check') }}
          </button>
        </div>
        <div class="grid gap-1 text-sm">
          <p v-if="linuxStatus?.host.available" class="text-slate-500">
            {{ linuxStatus.host.path }}
          </p>
          <p v-else-if="linuxStatus" class="text-red-600">
            {{ linuxStatus.host.reason }}
          </p>
        </div>
      </TabsContent>
    </TabsRoot>
  </section>
</template>
