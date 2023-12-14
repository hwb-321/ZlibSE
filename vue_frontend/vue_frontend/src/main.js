import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { getCookie, getCoverUrl } from '@/utils/utils';
import axios from 'axios';

// 创建一个新的 Axios 实例，专门用于获取 CSRF 令牌
const axiosInstance = axios.create();

axios.interceptors.request.use(async (config) => {
    if (!document.cookie.includes('csrftoken')) {
        // 使用新的 Axios 实例来获取 CSRF 令牌
        await axiosInstance.get(`${process.env.VUE_APP_BACKEND_URL}/user/init_csrf/`, { withCredentials: true });
        console.log('已成功获取csrf令牌');
        config.headers['X-CSRFToken'] = getCookie('csrftoken');
    } else {
        config.headers['X-CSRFToken'] = getCookie('csrftoken');
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

const app = createApp(App);

app.config.globalProperties.$getCookie = getCookie;
app.config.globalProperties.$getCoverUrl = getCoverUrl;

app.use(router).mount('#app');
