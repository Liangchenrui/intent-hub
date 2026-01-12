<template>
  <el-dropdown @command="handleCommand" trigger="click">
    <el-button type="text" class="language-switcher">
      <el-icon><Setting /></el-icon>
      <span>{{ currentLanguage }}</span>
      <el-icon class="el-icon--right"><ArrowDown /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="zh" :class="{ 'is-active': locale === 'zh' }">
          {{ $t('common.chinese') }}
        </el-dropdown-item>
        <el-dropdown-item command="en" :class="{ 'is-active': locale === 'en' }">
          {{ $t('common.english') }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { Setting, ArrowDown } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import en from 'element-plus/es/locale/lang/en';

const { locale, t } = useI18n();

const currentLanguage = computed(() => {
  return locale.value === 'zh' ? t('common.chinese') : t('common.english');
});

const handleCommand = (command: string) => {
  locale.value = command;
  localStorage.setItem('locale', command);
  
  // 更新 Element Plus 的语言
  const elementLocale = command === 'en' ? en : zhCn;
  // 注意：Element Plus 的语言需要全局更新，这里我们通过事件通知 main.ts
  window.dispatchEvent(new CustomEvent('locale-change', { detail: { locale: elementLocale } }));
  
  ElMessage.success(command === 'zh' ? '已切换到中文' : 'Switched to English');
};
</script>

<style scoped>
.language-switcher {
  color: var(--el-text-color-primary);
  padding: 0 12px;
  display: flex;
  align-items: center;
  gap: 4px;
}

:deep(.el-dropdown-menu__item.is-active) {
  color: var(--el-color-primary);
  font-weight: 600;
}
</style>

