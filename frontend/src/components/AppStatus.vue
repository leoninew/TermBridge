<script setup lang="ts">
import {
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuRoot,
} from 'reka-ui'
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
        <select
          v-model="locale"
          class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 shadow-sm outline-none transition focus:border-blue-500"
        >
          <option value="zh-CN">{{ t('app.language.zhCN') }}</option>
          <option value="en-US">{{ t('app.language.enUS') }}</option>
        </select>
      </label>
    </div>
  </header>
</template>
