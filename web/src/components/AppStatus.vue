<script setup lang="ts">
import {
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuRoot,
  SelectContent,
  SelectItem,
  SelectItemText,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { ChevronDown } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

const { locale, t } = useI18n()
const props = defineProps<{
  currentPath: string
}>()

const emit = defineEmits<{
  navigate: [path: string]
}>()

function isActive(path: string): boolean {
  return path === '/' ? props.currentPath === '/' : props.currentPath.startsWith(path)
}
</script>

<template>
  <header class="mb-4 flex flex-wrap items-center justify-between gap-4">
    <h1 class="text-lg font-semibold text-slate-950">{{ t('app.title') }}</h1>

    <div class="flex flex-wrap items-center gap-3">
      <NavigationMenuRoot orientation="horizontal">
        <NavigationMenuList class="flex items-center gap-1 text-sm text-slate-600">
          <NavigationMenuItem>
            <NavigationMenuLink
              as="button"
              :active="isActive('/')"
              class="border-b-2 border-transparent px-3 py-1.5 transition hover:border-slate-300 hover:text-slate-950 data-[active]:border-blue-600 data-[active]:text-blue-700"
              @select="emit('navigate', '/')"
            >
              {{ t('app.nav.sessions') }}
            </NavigationMenuLink>
          </NavigationMenuItem>
          <NavigationMenuItem>
            <NavigationMenuLink
              as="button"
              :active="isActive('/shortcuts')"
              class="border-b-2 border-transparent px-3 py-1.5 transition hover:border-slate-300 hover:text-slate-950 data-[active]:border-blue-600 data-[active]:text-blue-700"
              @select="emit('navigate', '/shortcuts')"
            >
              {{ t('app.nav.shortcuts') }}
            </NavigationMenuLink>
          </NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenuRoot>

      <label class="inline-flex items-center gap-2 text-sm text-slate-600">
        <span>{{ t('app.language.label') }}</span>
        <SelectRoot v-model="locale">
          <SelectTrigger
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 shadow-sm outline-none transition focus:border-blue-500"
          >
            <SelectValue />
            <ChevronDown class="h-4 w-4 shrink-0 text-slate-400" />
          </SelectTrigger>
          <SelectContent position="popper" class="z-50 min-w-[var(--reka-select-trigger-width)] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg shadow-blue-900/5">
            <SelectViewport class="p-1">
              <SelectItem
                value="zh-CN"
                class="cursor-pointer rounded-md px-3 py-2 text-sm outline-none hover:bg-blue-50 data-[highlighted]:bg-blue-50"
              >
                <SelectItemText>{{ t('app.language.zhCN') }}</SelectItemText>
              </SelectItem>
              <SelectItem
                value="en-US"
                class="cursor-pointer rounded-md px-3 py-2 text-sm outline-none hover:bg-blue-50 data-[highlighted]:bg-blue-50"
              >
                <SelectItemText>{{ t('app.language.enUS') }}</SelectItemText>
              </SelectItem>
            </SelectViewport>
          </SelectContent>
        </SelectRoot>
      </label>
    </div>
  </header>
</template>
