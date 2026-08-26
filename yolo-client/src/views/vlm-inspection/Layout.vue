<template>
  <div class="vlm-inspection-container">
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
.vlm-inspection-container {
  padding: 20px;
  height: 100%;
}
</style>
