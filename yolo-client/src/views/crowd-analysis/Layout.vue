<template>
  <div class="crowd-analysis-container">
    <router-view :key="routeKey" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const routeKey = computed(() => route.name + ':' + (route.params.id || ''))
</script>

<style scoped>
.crowd-analysis-container {
  padding: 20px;
  height: 100%;
}
</style>
