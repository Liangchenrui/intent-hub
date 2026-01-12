import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import router from './router'
import i18n from './i18n'

// 根据当前语言设置 Element Plus 的语言
const getElementLocale = () => {
  const locale = localStorage.getItem('locale') || 'zh';
  return locale === 'en' ? en : zhCn;
};

const app = createApp(App)
app.use(ElementPlus, {
  locale: getElementLocale(),
})
app.use(router)
app.use(i18n)
app.mount('#app')
