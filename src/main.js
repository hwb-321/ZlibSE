import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { getCoverUrl } from '@/utils/utils';
import { clearAccessToken, getAccessToken } from '@/utils/auth';
import axios from 'axios';
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'

const vuetify = createVuetify({
    components,
    directives,
})

axios.interceptors.request.use((config) => {
    const token = getAccessToken();
    if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

axios.interceptors.response.use((response) => response, async (error) => {
    if (error.response?.status === 401) {
        clearAccessToken();
        if (router.currentRoute.value.name !== 'LoginPage') {
            await router.push({ name: 'LoginPage' });
        }
    }
    return Promise.reject(error);
});

const app = createApp(App);

app.config.globalProperties.$getCoverUrl = getCoverUrl;

app.use(router).use(vuetify).mount('#app');
