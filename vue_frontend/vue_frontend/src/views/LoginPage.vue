<template>
    <v-container class="fill-height" fluid>
        <v-row align="center" justify="center">
            <v-col cols="12" sm="8" md="4">
                <v-card class="elevation-12">
                    <v-toolbar color="primary" dark flat>
                        <v-toolbar-title>登录</v-toolbar-title>
                    </v-toolbar>
                    <v-card-text>
                        <v-text-field label="用户名" prepend-icon="mdi-account" type="text" v-model="username"
                            required></v-text-field>
                        <v-text-field label="密码" prepend-icon="mdi-lock" type="password" v-model="password"
                            required></v-text-field>
                        <v-row no-gutters>
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

export default {
    data() {
        return {
            username: '',
            password: '',
            errorMessage: '',
            captchaKey: '',
            captchaValue: '',
            captchaImageUrl: '',
        };
    },
    methods: {
        async submitLogin() {
            try {
                const formData = new URLSearchParams();
                formData.append('captcha_key', this.captchaKey);
                formData.append('captcha_value', this.captchaValue);

                formData.append('username', this.username);
                formData.append('password', this.password);

                const response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/login_user`, formData, {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    withCredentials: true
                });

                if (response.data.success) {
                    this.$router.push('/home');
                } else {
                    this.errorMessage = response.data.error;
                }
            } catch (error) {
                console.error('Login error:', error);
                this.errorMessage = 'Login failed. Please try again.';
            }
        },
        async refreshCaptcha() {
            try {
                const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/user/generate_captcha`);
                this.captchaKey = response.data.key;
                this.captchaImageUrl = `${process.env.VUE_APP_BACKEND_URL}${response.data.image_url}`;
            } catch (error) {
                console.error('Error fetching captcha:', error);
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
        this.refreshCaptcha();
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