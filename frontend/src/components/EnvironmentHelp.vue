<script setup lang="ts">
import { ArrowLeft } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

const { locale, t } = useI18n()
</script>

<template>
  <main class="min-h-screen bg-slate-100 p-5 text-sm text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <section
      class="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-3xl flex-col p-6 md:p-10"
    >
      <RouterLink
        to="/"
        class="inline-flex items-center gap-2 self-start text-sm font-medium text-blue-700 hover:text-blue-800"
      >
        <ArrowLeft class="h-4 w-4" />
        {{ t('environmentHelp.back') }}
      </RouterLink>
      <div class="flex flex-1 items-center justify-center text-center">
        <h1 class="text-4xl font-semibold tracking-tight text-slate-950 dark:text-slate-100">
          {{ locale === 'zh-CN' ? '即将到来' : 'Comming Soon' }}
        </h1>
      </div>
    </section>
  </main>
</template>
