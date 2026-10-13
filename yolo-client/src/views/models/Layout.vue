<template>

  <div class="models-layout">

    <div class="layout-header">

      <h2>模型管理</h2>

      <el-tabs :model-value="activeTab" class="layout-tabs" @tab-change="handleTabChange">

        <el-tab-pane label="本地模型" name="list" />

        <el-tab-pane label="VLM 大模型" name="vlm" />

      </el-tabs>

    </div>

    <router-view />

  </div>

</template>



<script setup>

import { computed } from 'vue'

import { useRoute, useRouter } from 'vue-router'



const route = useRoute()

const router = useRouter()



const activeTab = computed(() => {

  if (route.path.includes('/models/vlm')) return 'vlm'

  return 'list'

})



const handleTabChange = (tabName) => {

  const pathMap = {

    list: '/models/list',

    vlm: '/models/vlm'

  }

  if (pathMap[tabName] && route.path !== pathMap[tabName]) {

    router.push(pathMap[tabName])

  }

}

</script>



<style scoped>

.models-layout {

  padding: 20px;

}



.layout-header {

  margin-bottom: 16px;

}



.layout-header h2 {

  margin: 0 0 12px;

}



.layout-tabs :deep(.el-tabs__header) {

  margin-bottom: 0;

}

</style>


