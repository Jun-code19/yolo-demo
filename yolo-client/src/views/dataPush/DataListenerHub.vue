<template>
  <div class="data-listener-hub">
    <el-tabs v-model="activePanel" class="hub-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="监听管理" name="configs">
        <DataListeners />
      </el-tab-pane>
      <el-tab-pane label="监听事件" name="events">
        <DataEvents />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DataListeners from './DataListeners.vue'
import DataEvents from './DataEvents.vue'

const route = useRoute()
const router = useRouter()
const activePanel = ref('configs')

const syncTabFromRoute = () => {
  activePanel.value = route.query.tab === 'events' ? 'events' : 'configs'
}

const handleTabChange = (tabName) => {
  const query = { ...route.query }
  if (tabName === 'events') {
    query.tab = 'events'
  } else {
    delete query.tab
  }
  router.replace({ path: '/data-listeners', query })
}

watch(() => route.query.tab, syncTabFromRoute)
onMounted(syncTabFromRoute)
</script>

<style scoped>
.data-listener-hub {
  padding: 0;
}

.hub-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}
</style>
