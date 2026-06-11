<script setup lang="ts">
import AppToast from './components/AppToast.vue'
import { useThemeStore } from './stores/theme'

useThemeStore()
</script>

<template>
  <RouterView />
  <AppToast />
</template>
