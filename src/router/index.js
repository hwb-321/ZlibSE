import { createRouter, createWebHistory } from 'vue-router';

// 引入组件
import HomePage from '../views/HomePage.vue';
import LoginPage from '../views/LoginPage.vue';
import UploadBookPage from '../views/UploadBookPage.vue';
import BookDetailPage from '@/views/BookDetailPage.vue'
import FavoritesPage from '@/views/FavoritesPage.vue';
import UploadedBookManagementPage from '@/views/UploadedBookManagementPage.vue';
import PersonalCenterPage from '@/views/PersonalCenterPage.vue';
import RegisterPage from '@/views/RegisterPage.vue';
import PasswordModificationPage from '@/views/PasswordModificationPage.vue';
import EpubReaderPage from '@/views/OnlineReader/EpubReaderPage.vue';
import ModifyBookInfoPage from '@/views/ModifyBookInfoPage.vue';

const routes = [
    {
        path: '/',
        name: 'HomePage',
        component: HomePage,
    },
    {
        path: '/login',
        name: 'LoginPage',
        component: LoginPage
    },
    {
        path: '/upload-book',
        name: 'UploadBookPage',
        component: UploadBookPage
    },
    {
        path: '/book/:bookId',
        name: 'BookDetail',
        component: BookDetailPage,
        props: true
    },
    {
        path: '/favorites',
        name: 'FavoritesPage',
        component: FavoritesPage
    },
    {
        path: '/uploaded-book-management',
        name: 'UploadedBookManagementPage',
        component: UploadedBookManagementPage
    },
    {
        path: '/personal-center',
        name: 'PersonalCenterPage',
        component: PersonalCenterPage
    },
    {
        path: '/register',
        name: 'RegisterPage',
        component: RegisterPage
    },
    {
        path: '/change-password',
        name: 'PasswordModificationPage',
        component: PasswordModificationPage
    },
    {
        path: '/online-reader-epub',
        name: 'EpubReaderPage',
        component: EpubReaderPage
    },
    {
        path: '/modify-book/:bookId',
        name: 'ModifyBookInfoPage',
        component: ModifyBookInfoPage
    }
];

const router = createRouter({
    history: createWebHistory(process.env.BASE_URL),
    routes
});

router.beforeEach((to, from, next) => {
    next();
});

export default router;
