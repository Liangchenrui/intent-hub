<template>
  <el-container class="layout-container">
    <el-header class="header-wrapper">
      <div class="header-content">
        <div class="brand">
          <img src="@/assets/logo.png" alt="Intent Hub" class="logo-img" />
        </div>
        <div class="user-info">
          <LanguageSwitcher />
          <el-button type="danger" @click="handleLogout">{{ $t('common.logout') }}</el-button>
        </div>
      </div>
    </el-header>

    <el-main class="main-wrapper">
      <div class="page-header">
        <el-tabs v-model="activeTab" class="nav-tabs" @tab-change="handleTabChange">
          <el-tab-pane :label="$t('nav.list')" name="list"></el-tab-pane>
          <el-tab-pane :label="$t('nav.test')" name="test"></el-tab-pane>
          <el-tab-pane :label="$t('nav.diagnostics')" name="diagnostics"></el-tab-pane>
          <el-tab-pane :label="$t('nav.settings')" name="settings"></el-tab-pane>
        </el-tabs>
      </div>

      <el-card shadow="never" class="content-card">
        <div class="diagnostic-header">
          <div class="title-section">
            <h2>{{ $t('diagnostics.title') }}</h2>
            <p class="description">{{ $t('diagnostics.description') }}</p>
          </div>
          <div class="action-section">
            <el-segmented
              v-model="viewMode"
              :options="viewOptions"
              size="small"
            />
            <div class="threshold-control">
              <span>{{ $t('diagnostics.threshold') }}</span>
              <el-slider 
                v-model="threshold" 
                :min="0.5" 
                :max="1" 
                :step="0.01" 
                style="width: 150px; margin: 0 15px"
              />
              <el-tag>{{ threshold }}</el-tag>
            </div>
            <el-button 
              type="primary" 
              :icon="Search" 
              @click="runDiagnostics" 
              :loading="loading"
            >
              {{ $t('diagnostics.refresh') }}
            </el-button>
          </div>
        </div>

        <div v-if="viewMode === 'map'" class="map-panel">
          <div class="map-toolbar">
            <div class="map-controls">
              <span class="control-label">{{ $t('diagnostics.nNeighbors') }}</span>
              <el-input-number v-model="umapNeighbors" :min="2" :max="100" :step="1" size="small" />
              <span class="control-label">{{ $t('diagnostics.minDist') }}</span>
              <el-input-number v-model="umapMinDist" :min="0" :max="1" :step="0.05" :precision="2" size="small" />
            </div>
            <el-button :loading="mapLoading" @click="loadUmap" type="primary" plain>
              {{ $t('diagnostics.loadMap') }}
            </el-button>
          </div>

          <div class="map-chart-wrap" v-loading="mapLoading">
            <div ref="chartRef" class="map-chart"></div>
          </div>
        </div>

        <div v-else-if="!loading && results.length === 0" class="empty-state">
          <el-empty :description="$t('diagnostics.noOverlap')">
            <template #image>
              <el-icon :size="60" color="#67C23A"><CircleCheckFilled /></el-icon>
            </template>
          </el-empty>
        </div>

        <div v-else class="results-container" v-loading="loading">
          <div v-for="(result, index) in results" :key="index" class="conflict-group">
            <h3 class="source-route">
              <el-icon><Warning /></el-icon>
              {{ result.route_name }}
            </h3>
            
            <el-table :data="result.overlaps" style="width: 100%" class="overlap-table">
              <el-table-column prop="target_route_name" :label="$t('diagnostics.targetRoute')" min-width="150" />
              <el-table-column :label="$t('diagnostics.score')" width="120">
                <template #default="{ row }">
                  <el-progress 
                    :percentage="Math.round(row.overlap_score * 100)" 
                    :status="row.overlap_score > 0.9 ? 'exception' : 'warning'"
                  />
                </template>
              </el-table-column>
              <el-table-column :label="$t('diagnostics.conflictingUtterances')" min-width="300">
                <template #default="{ row }">
                  <div class="conflicting-utterances">
                    <el-tag 
                      v-for="(utt, uIdx) in row.conflicting_utterances" 
                      :key="uIdx"
                      class="utt-tag"
                      size="small"
                      type="danger"
                      effect="plain"
                    >
                      {{ utt.utterance }} ({{ Math.round(utt.similarity * 100) }}%)
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column width="150">
                <template #default>
                  <el-button size="small" disabled>{{ $t('diagnostics.fixing') }}</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, nextTick, onBeforeUnmount, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Warning, CircleCheckFilled } from '@element-plus/icons-vue';
import * as echarts from 'echarts';
import { getOverlaps, getUmapPoints, type DiagnosticResult, type UmapPoint2D } from '../api';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';

const { t } = useI18n();
const router = useRouter();

const activeTab = ref('diagnostics');
const threshold = ref(0.85);
const loading = ref(false);
const results = ref<DiagnosticResult[]>([]);

const viewMode = ref<'list' | 'map'>('list');
const viewOptions = computed(() => [
  { label: t('diagnostics.listView'), value: 'list' },
  { label: t('diagnostics.mapView'), value: 'map' },
]);

const mapLoading = ref(false);
const umapNeighbors = ref(15);
const umapMinDist = ref(0.1);
const chartRef = ref<HTMLDivElement | null>(null);
const umapPoints = ref<UmapPoint2D[]>([]);
const chartInstance = ref<echarts.ECharts | null>(null);

// 颜色映射：为每个路由分配稳定颜色
const colorByRoute = ref<Record<number, string>>({});
const routeNames = ref<Record<number, string>>({});

const runDiagnostics = async () => {
  loading.value = true;
  try {
    const response = await getOverlaps(threshold.value);
    results.value = response.data;
    if (results.value.length > 0) {
      ElMessage.warning(t('diagnostics.overlapDetected', { count: results.value.length }));
    } else {
      ElMessage.success(t('diagnostics.noOverlap'));
    }
  } catch (error) {
    ElMessage.error(t('agent.fetchError'));
  } finally {
    loading.value = false;
  }
};

const getColorForRoute = (routeId: number): string => {
  if (colorByRoute.value[routeId]) return colorByRoute.value[routeId];
  // 稳定哈希到色相，生成鲜艳但易区分的颜色
  const hue = (routeId * 137.508) % 360; // 使用黄金角度确保分布均匀
  const saturation = 65 + (routeId % 3) * 10; // 65-85%
  const lightness = 45 + (routeId % 2) * 10; // 45-55%
  const color = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  colorByRoute.value[routeId] = color;
  return color;
};

const initChart = async () => {
  await nextTick();
  const chartDom = chartRef.value;
  if (!chartDom) return;

  // 如果已存在实例，先销毁
  if (chartInstance.value) {
    chartInstance.value.dispose();
  }

  chartInstance.value = echarts.init(chartDom);
  
  // 监听窗口大小变化
  const resizeHandler = () => {
    chartInstance.value?.resize();
  };
  window.addEventListener('resize', resizeHandler);
  
  // 在组件卸载时清理
  onBeforeUnmount(() => {
    window.removeEventListener('resize', resizeHandler);
    if (chartInstance.value) {
      chartInstance.value.dispose();
      chartInstance.value = null;
    }
  });

  updateChart();
};

const updateChart = () => {
  if (!chartInstance.value || !umapPoints.value.length) return;

  // 按路由分组数据
  const routeGroups: Record<number, Array<[number, number, UmapPoint2D]>> = {};
  const routeIdSet = new Set<number>();

  umapPoints.value.forEach(point => {
    const routeId = point.route_id;
    routeIdSet.add(routeId);
    if (!routeGroups[routeId]) {
      routeGroups[routeId] = [];
      routeNames.value[routeId] = point.route_name || `Route ${routeId}`;
    }
    routeGroups[routeId].push([point.x, point.y, point]);
  });

  // 构建 ECharts series 数据
  const series = Array.from(routeIdSet).map(routeId => ({
    name: routeNames.value[routeId],
    type: 'scatter',
    data: routeGroups[routeId].map(([x, y, point]) => ({
      value: [x, y],
      routeId: point.route_id,
      routeName: point.route_name,
      utterance: point.utterance,
    })),
    symbolSize: 8,
    itemStyle: {
      color: getColorForRoute(routeId),
      opacity: 0.75,
    },
    emphasis: {
      itemStyle: {
        opacity: 1,
        borderColor: '#333',
        borderWidth: 2,
      },
    },
  }));

  const option: echarts.EChartsOption = {
    title: {
      text: t('diagnostics.mapTitle'),
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'normal',
      },
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (Array.isArray(params)) {
          return params.map(p => {
            const data = p.data;
            return `<div style="margin-bottom: 4px;">
              <strong style="color: ${p.color};">${data.routeName || `Route ${data.routeId}`}</strong><br/>
              <span style="font-size: 12px; color: #666;">${data.utterance}</span>
            </div>`;
          }).join('<hr style="margin: 4px 0; border: none; border-top: 1px solid #eee;"/>');
        }
        const data = params.data;
        return `<div>
          <strong style="color: ${params.color};">${data.routeName || `Route ${data.routeId}`}</strong><br/>
          <span style="font-size: 12px; color: #666;">${data.utterance}</span>
        </div>`;
      },
      backgroundColor: 'rgba(50, 50, 50, 0.9)',
      borderColor: '#333',
      borderWidth: 1,
      textStyle: {
        color: '#fff',
      },
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 20,
      top: 60,
      bottom: 20,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: {
        fontSize: 12,
      },
      selectedMode: 'multiple', // 支持点击图例筛选
    },
    grid: {
      left: '3%',
      right: '20%',
      top: '15%',
      bottom: '10%',
      containLabel: false,
    },
    xAxis: {
      type: 'value',
      name: 'UMAP X',
      nameLocation: 'middle',
      nameGap: 30,
      scale: true,
      splitLine: {
        show: true,
        lineStyle: {
          type: 'dashed',
          opacity: 0.3,
        },
      },
    },
    yAxis: {
      type: 'value',
      name: 'UMAP Y',
      nameLocation: 'middle',
      nameGap: 50,
      scale: true,
      splitLine: {
        show: true,
        lineStyle: {
          type: 'dashed',
          opacity: 0.3,
        },
      },
    },
    dataZoom: [
      {
        type: 'slider',
        show: true,
        xAxisIndex: [0],
        start: 0,
        end: 100,
        height: 20,
        bottom: 10,
      },
      {
        type: 'slider',
        show: true,
        yAxisIndex: [0],
        start: 0,
        end: 100,
        width: 20,
        left: 10,
      },
      {
        type: 'inside',
        xAxisIndex: [0],
      },
      {
        type: 'inside',
        yAxisIndex: [0],
      },
    ],
    series,
  };

  chartInstance.value.setOption(option, true);
};

const loadUmap = async () => {
  mapLoading.value = true;
  try {
    const response = await getUmapPoints({ 
      n_neighbors: umapNeighbors.value, 
      min_dist: umapMinDist.value, 
      seed: 42 
    });
    umapPoints.value = response.data.points || [];
    if (!umapPoints.value.length) {
      ElMessage.info(t('diagnostics.noData'));
      return;
    }
    
    // 初始化图表（如果尚未初始化）
    if (!chartInstance.value) {
      await initChart();
    } else {
      updateChart();
    }
    
    ElMessage.success(t('diagnostics.mapLoaded', { count: umapPoints.value.length }));
  } catch (e) {
    ElMessage.error(t('agent.fetchError'));
  } finally {
    mapLoading.value = false;
  }
};

// 监听视图模式切换，切换到 map 时初始化图表
watch(viewMode, async (newMode) => {
  if (newMode === 'map' && umapPoints.value.length > 0) {
    await nextTick();
    await initChart();
  }
});

const handleTabChange = (tabName: any) => {
  if (tabName === 'list') {
    router.push('/');
  } else if (tabName === 'test') {
    router.push('/test');
  } else if (tabName === 'diagnostics') {
    router.push('/diagnostics');
  } else if (tabName === 'settings') {
    router.push('/settings');
  }
};

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm(t('agent.logoutConfirm'), t('agent.logoutTitle'), { type: 'warning' });
    localStorage.removeItem('api_key');
    router.push('/login');
  } catch (e) {}
};

onMounted(() => {
  runDiagnostics();
  // 如果初始视图是 map，延迟初始化图表（等待 DOM 渲染）
  if (viewMode.value === 'map') {
    nextTick(() => {
      initChart();
    });
  }
});
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  background-color: #f5f7fa;
}

.header-wrapper {
  background-color: #fff;
  border-bottom: 1px solid #e6e8eb;
  padding: 0 40px;
  height: 64px !important;
  display: flex;
  align-items: center;
}

.header-content {
  width: 95%;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo-img {
  height: 40px;
}

.main-wrapper {
  width: 95%;
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 0;
}

.page-header {
  margin-bottom: 24px;
}

.nav-tabs :deep(.el-tabs__item) {
  min-width: 120px;
  font-size: 15px;
}

.content-card {
  border-radius: 12px;
}

.diagnostic-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f0f0f0;
}

.title-section h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
}

.description {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.action-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.threshold-control {
  display: flex;
  align-items: center;
  font-size: 14px;
  color: #606266;
}

.conflict-group {
  margin-bottom: 40px;
}

.source-route {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 15px;
  font-size: 18px;
  color: #E6A23C;
}

.conflicting-utterances {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.utt-tag {
  height: auto;
  padding: 4px 8px;
  white-space: normal;
  max-width: 250px;
  line-height: 1.4;
}

.empty-state {
  padding: 60px 0;
}

.map-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.map-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.map-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.control-label {
  font-size: 12px;
  color: #606266;
}

.map-chart-wrap {
  width: 100%;
  height: 600px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
}

.map-chart {
  width: 100%;
  height: 100%;
}
</style>
