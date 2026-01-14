<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="login-header">
          <img src="@/assets/logo.png" alt="Intent Hub" class="login-logo" />
        </div>
      </template>
      <el-form :model="{ sername, password }" @submit.prevent="handleLogin" label-position="top">
        <el-form-item :label="$t('login.username')">
          <el-input 
            v-model="username" 
            :placeholder="$t('login.usernamePlaceholder')" 
            clearable
          />
        </el-form-item>
        <el-form-item :label="$t('login.password')">
          <el-input 
            v-model="password" 
            type="password" 
            :placeholder="$t('login.passwordPlaceholder')" 
            show-password
          />
        </el-form-item>
        
        <div v-if="error" class="error-msg">
          <el-alert :title="error" type="error" :closable="false" show-icon />
        </div>

        <el-button 
          type="primary" 
          native-type="submit" 
          :loading="loading" 
          class="login-btn"
          size="large"
        >
          {{ loading ? $t('login.logging') : $t('login.login') }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import api from '../api';

const { t } = useI18n();

const username = ref('admin');
const password = ref('123456');
const loading = ref(false);
const error = ref('');
const router = useRouter();

const handleLogin = async () => {
  loading.value = true;
  error.value = '';
  
  try {
    const response = await api.post('/auth/login', {
      username: username.value,
      password: password.value,
    });
    
    const { api_key } = response.data;
    if (api_key) {
      localStorage.setItem('api_key', api_key);
      router.push('/');
    } else {
      error.value = t('login.serverError');
    }
  } catch (err: any) {
    if (err.response) {
      error.value = err.response.data?.detail || err.response.data?.error || t('login.loginFailed');
    } else if (err.request) {
      error.value = t('login.connectionError');
    } else {
      error.value = t('login.requestError');
    }
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: var(--el-bg-color-page);
}

.login-card {
  width: 100%;
  max-width: 400px;
}

.login-header {
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
}

.login-logo {
  max-width: 200px;
  height: auto;
}

.login-btn {
  width: 100%;
  margin-top: 20px;
}

.error-msg {
  margin-bottom: 20px;
}
</style>
