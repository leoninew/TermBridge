import { createRouter, createWebHistory } from 'vue-router'
import AppShell from './components/AppShell.vue'
import EnvironmentHelp from './components/EnvironmentHelp.vue'
import EnvironmentManagement from './components/EnvironmentManagement.vue'
import HomeOnboarding from './components/HomeOnboarding.vue'
import SessionTerminal from './components/SessionTerminal.vue'
import ShortcutManagement from './components/ShortcutManagement.vue'
import { useEnvironmentStore } from './stores/environment'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeOnboarding },
    { path: '/help', component: EnvironmentHelp },
    {
      path: '/',
      component: AppShell,
      children: [
        { path: 'session', component: SessionTerminal },
        { path: 'environment', component: EnvironmentManagement },
        { path: 'shortcuts', component: ShortcutManagement },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (to.path !== '/' && to.path !== '/session') {
    return
  }

  const environmentStore = useEnvironmentStore()
  if (!environmentStore.loaded && !environmentStore.loading) {
    await environmentStore.load()
  }

  if (to.path === '/' && environmentStore.hasReadyEnvironment) {
    return '/session'
  }

  if (to.path === '/session' && !environmentStore.hasReadyEnvironment) {
    return '/'
  }
})
