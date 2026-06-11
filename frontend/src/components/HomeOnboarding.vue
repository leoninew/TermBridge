<script setup lang="ts">
import type { Component } from 'vue'
import { BookOpen, ChevronRight, Loader2 } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import CygwinLogo from './CygwinLogo.vue'
import LinuxLogo from './LinuxLogo.vue'
import WslLogo from './WslLogo.vue'
import { useEnvironmentStore } from '../stores/environment'
import type { ShortcutHost } from '../types/sessions'

const { t } = useI18n()
const environmentStore = useEnvironmentStore()

const options: Array<{ host: ShortcutHost; icon: Component; titleKey: string; descriptionKey: string }> = [
  {
    host: 'windows_cygwin',
    icon: CygwinLogo,
    titleKey: 'homeOnboarding.environments.windowsCygwin.title',
    descriptionKey: 'homeOnboarding.environments.windowsCygwin.description',
  },
  {
    host: 'windows_wsl',
    icon: WslLogo,
    titleKey: 'homeOnboarding.environments.windowsWsl.title',
    descriptionKey: 'homeOnboarding.environments.windowsWsl.description',
  },
  {
    host: 'linux',
    icon: LinuxLogo,
    titleKey: 'homeOnboarding.environments.linux.title',
    descriptionKey: 'homeOnboarding.environments.linux.description',
  },
]
</script>

<template>
  <main class="min-h-screen bg-slate-100 p-5 text-sm text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <section
      class="mx-auto grid min-h-[calc(100vh-2.5rem)] max-w-6xl content-center gap-8 p-6 md:p-10"
    >
      <div class="mx-auto max-w-3xl text-center">
        <h1 class="text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl dark:text-slate-100">
          {{ t('homeOnboarding.title') }}
        </h1>
        <p class="mt-4 text-base leading-7 text-slate-600 dark:text-slate-400">
          {{ t('homeOnboarding.description') }}
        </p>
        <p
          v-if="environmentStore.loading"
          class="mt-4 inline-flex items-center gap-2 border-l border-slate-200 bg-white/40 px-4 py-2 text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400"
        >
          <Loader2 class="h-4 w-4 animate-spin" />
          {{ t('homeOnboarding.loading') }}
        </p>
        <p v-else-if="environmentStore.error" class="mt-4 border-l border-red-300 bg-red-50/70 px-4 py-3 text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          {{ environmentStore.error }}
        </p>
      </div>

      <div class="grid gap-4 md:grid-cols-3">
        <RouterLink
          v-for="option in options"
          :key="option.host"
          :to="{ path: '/environment', query: { tab: option.host } }"
          class="group grid min-h-44 gap-4 border border-slate-200 bg-white/35 p-5 text-left transition hover:border-blue-400 hover:bg-white/70 dark:border-slate-800 dark:bg-slate-950 dark:hover:border-blue-500 dark:hover:bg-slate-900/50"
        >
          <span class="inline-flex h-11 w-11 items-center justify-center rounded-lg bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300">
            <component :is="option.icon" class="h-5 w-5" />
          </span>
          <span>
            <span class="block text-lg font-semibold text-slate-950 dark:text-slate-100">{{ t(option.titleKey) }}</span>
            <span class="mt-2 block leading-6 text-slate-600 dark:text-slate-400">{{ t(option.descriptionKey) }}</span>
          </span>
          <span class="mt-auto inline-flex items-center gap-1 font-medium text-blue-700 dark:text-blue-400">
            {{ t('homeOnboarding.configure') }}
            <ChevronRight class="h-4 w-4 transition group-hover:translate-x-0.5" />
          </span>
        </RouterLink>
      </div>

      <div class="mx-auto flex flex-wrap items-center justify-center gap-3 text-slate-600 dark:text-slate-400">
        <BookOpen class="h-4 w-4" />
        <span>{{ t('homeOnboarding.docsPrompt') }}</span>
        <RouterLink class="font-medium text-blue-700 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300" to="/help">
          {{ t('homeOnboarding.docsLink') }}
        </RouterLink>
      </div>
    </section>
  </main>
</template>
