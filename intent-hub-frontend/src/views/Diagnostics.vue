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

        <div v-if="!loading && results.length === 0" class="empty-state">
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
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Warning, CircleCheckFilled } from '@element-plus/icons-vue';
import { getOverlaps, type DiagnosticResult } from '../api';
import LanguageSwitcher from '../components/LanguageSwitcher.vue';

const { t } = useI18n();
const router = useRouter();

const activeTab = ref('diagnostics');
const threshold = ref(0.85);
const loading = ref(false);
const results = ref<DiagnosticResult[]>([]);

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

const handleTabChange = (tabName: any) => {
  if (tabName === 'list') {
    router.push('/');
  } else if (tabName === 'test') {
    router.push('/test');
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
</style>
