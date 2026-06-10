<script setup lang="ts">
import { AlertCircle, Check, ChevronRight, Languages, Loader2, Plus, Settings } from '@lucide/vue'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuRoot,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from 'reka-ui'
import { useI18n } from 'vue-i18n'
import type { Session } from '../types/sessions'
import SessionCard from './SessionCard.vue'

const { locale, t } = useI18n()

defineProps<{
  sessions: Session[]
  activeSessionId?: string
  loading: boolean
  error: string
  compact?: boolean
}>()

const emit = defineEmits<{
  create: []
  collapse: []
  select: [session: Session]
  restart: [session: Session]
  remove: [session: Session]
  navigate: [path: string]
}>()
</script>

<template>
  <section
    class="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-blue-900/5"
  >
    <div class="flex items-center justify-between gap-3 p-4 pb-2">
      <h2 class="text-lg font-semibold text-slate-950">{{ t('session.list.title') }}</h2>
      <button
        type="button"
        class="inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-blue-600 px-3 py-2 text-sm text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
        @click="emit('create')"
      >
        <Plus class="h-4 w-4" />
        {{ t('session.list.createLabel') }}
      </button>
    </div>

    <div class="flex min-h-0 flex-1 flex-col gap-3 p-4 pt-2">
      <p v-if="loading" class="inline-flex items-center gap-2 text-sm text-slate-500">
        <Loader2 class="h-4 w-4 animate-spin" />
        {{ t('session.list.loading') }}
      </p>
      <p v-else-if="error" class="inline-flex items-center gap-2 text-sm text-red-600">
        <AlertCircle class="h-4 w-4" />
        {{ error }}
      </p>
      <p v-else-if="sessions.length === 0" class="text-sm text-slate-500">
        {{ t('session.list.empty') }}
      </p>
      <div v-else class="grid min-h-0 flex-1 content-start gap-2.5 overflow-auto pr-1">
        <SessionCard
          v-for="session in sessions"
          :key="session.id"
          :session="session"
          :active="session.id === activeSessionId"
          :compact="compact"
          @select="emit('select', $event)"
          @restart="emit('restart', $event)"
          @remove="emit('remove', $event)"
        />
      </div>
    </div>

    <div class="mt-auto border-t border-slate-200 p-3">
      <DropdownMenuRoot>
        <DropdownMenuTrigger
          class="inline-flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-slate-600 transition hover:bg-slate-50 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
        >
          <Settings class="h-4 w-4" />
          {{ t('app.settings.trigger') }}
        </DropdownMenuTrigger>
        <DropdownMenuPortal>
          <DropdownMenuContent
            :side-offset="8"
            align="start"
            side="top"
            class="z-50 min-w-56 rounded-xl border border-slate-200 bg-white p-1 text-sm text-slate-700 shadow-xl shadow-blue-900/10"
          >
            <DropdownMenuLabel class="px-3 py-2 text-sm uppercase tracking-wide text-slate-400">
              {{ t('app.settings.navigation') }}
            </DropdownMenuLabel>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
              @select="emit('navigate', '/environment')"
            >
              {{ t('app.nav.environment') }}
              <ChevronRight class="h-4 w-4 text-slate-400" />
            </DropdownMenuItem>
            <DropdownMenuItem
              class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
              @select="emit('navigate', '/shortcuts')"
            >
              {{ t('app.nav.shortcuts') }}
              <ChevronRight class="h-4 w-4 text-slate-400" />
            </DropdownMenuItem>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger
                class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
              >
                <span class="inline-flex items-center gap-2">
                  <Languages class="h-4 w-4 text-slate-500" />
                  {{ t('app.language.label') }}
                </span>
                <ChevronRight class="h-4 w-4 text-slate-400" />
              </DropdownMenuSubTrigger>
              <DropdownMenuPortal>
                <DropdownMenuSubContent
                  :side-offset="8"
                  class="z-50 min-w-40 rounded-xl border border-slate-200 bg-white p-1 text-sm text-slate-700 shadow-xl shadow-blue-900/10"
                >
                  <DropdownMenuRadioGroup v-model="locale">
                    <DropdownMenuRadioItem
                      value="zh-CN"
                      class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
                    >
                      <Check
                        :class="locale === 'zh-CN' ? 'opacity-100' : 'opacity-0'"
                        class="h-4 w-4 text-blue-600"
                      />
                      {{ t('app.language.zhCN') }}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem
                      value="en-US"
                      class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 outline-none hover:bg-blue-50 focus:bg-blue-50"
                    >
                      <Check
                        :class="locale === 'en-US' ? 'opacity-100' : 'opacity-0'"
                        class="h-4 w-4 text-blue-600"
                      />
                      {{ t('app.language.enUS') }}
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuPortal>
            </DropdownMenuSub>
          </DropdownMenuContent>
        </DropdownMenuPortal>
      </DropdownMenuRoot>
    </div>
  </section>
</template>
