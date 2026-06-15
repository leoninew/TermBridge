import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { listEnvironments } from '../api/sessions'
import type { EnvironmentSummary } from '../types/sessions'

export const useEnvironmentStore = defineStore('environment', () => {
  const environments = ref<EnvironmentSummary[]>([])
  const loading = ref(false)
  const error = ref('')
  const loaded = ref(false)
  const hasReadyEnvironment = computed(() =>
    environments.value.some(
      (environment) => environment.readiness === 'ready' && environment.available_on_host,
    ),
  )
  let loadPromise: Promise<void> | undefined

  async function load() {
    if (loadPromise) {
      return loadPromise
    }

    loading.value = true
    error.value = ''
    loadPromise = (async () => {
      try {
        environments.value = (await listEnvironments()).environments
        loaded.value = true
      } catch (err) {
        error.value = err instanceof Error ? err.message : 'Failed to load environments'
      } finally {
        loading.value = false
        loadPromise = undefined
      }
    })()
    return loadPromise
  }

  async function ensureLoaded() {
    if (loaded.value) {
      return
    }
    await load()
  }

  function update(nextEnvironments: EnvironmentSummary[]) {
    environments.value = nextEnvironments
    loaded.value = true
    error.value = ''
  }

  return { environments, loading, error, loaded, hasReadyEnvironment, load, ensureLoaded, update }
})
