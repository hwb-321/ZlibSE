<template>
    <v-container class="fill-height" fluid>
        <v-row align="center" justify="center">
            <v-col cols="12" sm="8" md="6">
                <v-card class="elevation-12">
                    <v-toolbar color="primary" dark flat>
                        <v-toolbar-title>登录</v-toolbar-title>
                    </v-toolbar>
                    <v-card-text>
                        <v-text-field label="用户名" prepend-icon="mdi-account" type="text" v-model="username"
                            required></v-text-field>
                        <v-text-field label="密码" prepend-icon="mdi-lock" type="password" v-model="password"
                            required></v-text-field>
                        <v-row v-if="captchaEnabled" no-gutters>
                            <v-col cols="9">
                                <v-text-field label="验证码" prepend-icon="mdi-shield-key" type="text" v-model="captchaValue"
                                    required></v-text-field>
                            </v-col>
                            <v-col cols="3">
                                <div class="captcha-container">
                                    <img :src="captchaImageUrl" @click="refreshCaptcha" />
                                </div>
                            </v-col>
                        </v-row>

                    </v-card-text>
                    <v-card-actions>
                        <v-spacer></v-spacer>
                        <v-btn color="primary" @click="submitLogin">登录</v-btn>
                    </v-card-actions>
                    <v-card-actions>
                        <v-spacer></v-spacer>
                        <!-- 使用 @click.middle 捕获鼠标中键事件 -->
                        <v-btn color="green" @click="openRegisterPage" @click.middle.prevent="openRegisterPageInNewTab">注册
                            <v-icon icon="mdi-open-in-new" right></v-icon>
                        </v-btn>
                    </v-card-actions>
                    <v-alert type="error" v-if="errorMessage" class="mt-4">
                        {{ errorMessage }}
                    </v-alert>
                </v-card>
            </v-col>
        </v-row>
    </v-container>
</template>
  
<script>
import axios from 'axios';
import appConfig from '@/config/appConfig.json';
import { setAccessToken } from '@/utils/auth';

export default {
    data() {
        return {
            username: '',
            password: '',
            errorMessage: '',
            captchaEnabled: true,
            captchaKey: '',
            captchaValue: '',
            captchaImageUrl: '',
        };
    },
    methods: {
        async initCaptcha() {
            try {
                const response = await axios.get(`${appConfig.backendUrl}/user/generate_captcha`);
                this.captchaEnabled = response.data.captchaEnabled !== false;
                if (this.captchaEnabled) {
                    this.captchaKey = response.data.key || '';
                    this.captchaImageUrl = response.data.image_url
                        ? `${appConfig.backendUrl}${response.data.image_url}`
                        : '';
                } else {
                    this.captchaKey = '';
                    this.captchaValue = '';
                    this.captchaImageUrl = '';
                }
            } catch (error) {
                console.error('初始化验证码配置失败：', error);
                this.captchaEnabled = true;
                await this.refreshCaptcha();
            }
        },
        async submitLogin() {
            try {
                const formData = new URLSearchParams();
                formData.append('captcha_key', this.captchaKey);
                formData.append('captcha_value', this.captchaValue);

                formData.append('username', this.username);
                formData.append('password', this.password);

                const response = await axios.post(`${appConfig.backendUrl}/user/login_user`, formData, {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                });

                if (response.data.success) {
                    setAccessToken(response.data.access_token);
                    this.$router.push('/');
                } else {
                    this.errorMessage = response.data.error;
                }
            } catch (error) {
                console.error('Login error:', error);
                this.errorMessage = '登陆失败，请重试。';
            }
        },
        async refreshCaptcha() {
            try {
                const response = await axios.get(`${appConfig.backendUrl}/user/generate_captcha`);
                this.captchaEnabled = response.data.captchaEnabled !== false;
                if (!this.captchaEnabled) {
                    this.captchaKey = '';
                    this.captchaValue = '';
                    this.captchaImageUrl = '';
                    return;
                }
                this.captchaKey = response.data.key || '';
                this.captchaImageUrl = response.data.image_url
                    ? `${appConfig.backendUrl}${response.data.image_url}`
                    : '';
            } catch (error) {
                console.error('获取验证码错误：', error);
            }
        },
        openRegisterPage() {
            this.$router.push({ name: 'RegisterPage' });
        },
        openRegisterPageInNewTab() {
            const routeData = this.$router.resolve({ name: 'RegisterPage' });
            window.open(routeData.href, '_blank');
        },
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '登录';
        });
        this.initCaptcha();
    },
};
</script>

<style scoped>
.v-btn {
    font-size: 17px;
}

.captcha-container img {
    cursor: pointer;
    height: 50px;
    /* 根据需要调整大小 */
}
</style>
