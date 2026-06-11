import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'termbridge.theme'

function isThemeMode(value: string | null): value is ThemeMode {
  return value === 'light' || value === 'dark'
}

function initialTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light'
  }
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return isThemeMode(stored) ? stored : 'light'
}

function applyTheme(mode: ThemeMode) {
  document.documentElement.dataset.theme = mode
  document.documentElement.classList.toggle('dark', mode === 'dark')
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(initialTheme())

  applyTheme(mode.value)

  watch(mode, (nextMode) => {
    window.localStorage.setItem(STORAGE_KEY, nextMode)
    applyTheme(nextMode)
  })

  return { mode }
})
