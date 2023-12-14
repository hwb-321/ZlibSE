import { createRouter, createWebHistory } from 'vue-router';
import axios from 'axios';

// 引入组件
import HomePage from '../views/HomePage.vue';
import LoginPage from '../views/LoginPage.vue';
import UploadBookPage from '../views/UploadBookPage.vue';
import BookDetailPage from '@/views/BookDetailPage.vue'

// 定义路由
// 每个路由都需要映射到一个组件
const routes = [
    {
        path: '/',
        name: 'LoginPage',
        component: LoginPage
    },
    {
        path: '/home',
        name: 'HomePage',
        component: HomePage
    },
    {
        path: '/upload-book',
        name: 'UploadBookPage',
        component: UploadBookPage
    },
    {
        path: '/book/:id',
        name: 'BookDetail',
        component: BookDetailPage,
        props: true
    }
];

const router = createRouter({
    history: createWebHistory(process.env.BASE_URL),
    routes
});

router.beforeEach(async (to, from, next) => {
    try {
        const sessionResponse = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/user/check_session/`, { withCredentials: true });

        if (sessionResponse.data.isLoggedIn) {
            // 如果用户已登录且当前在登录页面，则跳转到主页面
            if (to.name === 'LoginPage') {
                next({ name: 'HomePage' });
            } else {
                next();
            }
        } else {
            // 如果用户未登录，则强制跳转到登录页面
            if (to.name !== 'LoginPage') {
                next({ name: 'LoginPage' });
            } else {
                next();
            }
        }
    } catch (error) {
        // 处理错误，例如网络问题等
        console.error('Error checking session:', error);
        next({ name: 'LoginPage' });
    }
});

export default router;
