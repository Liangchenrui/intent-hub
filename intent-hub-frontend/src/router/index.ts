import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/Login.vue';
import AgentList from '../views/AgentList.vue';
import AgentTest from '../views/AgentTest.vue';
import Settings from '../views/Settings.vue';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { public: true }
  },
  {
    path: '/',
    name: 'AgentList',
    component: AgentList,
  },
  {
    path: '/test',
    name: 'AgentTest',
    component: AgentTest,
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('api_key');
  if (!to.meta.public && !token) {
    next({ name: 'Login' });
  } else {
    next();
  }
});

export default router;


