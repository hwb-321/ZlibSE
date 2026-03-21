<template>
    <v-container class="fill-height" fluid>
        <v-row align="center" justify="center">
            <v-col cols="12" sm="8" md="6">
                <v-card class="elevation-12">
                    <v-toolbar color="primary" dark flat>
                        <v-toolbar-title>注册</v-toolbar-title>
                    </v-toolbar>
                    <v-card-text>
                        <v-form ref="form" @submit.prevent="register">
                            <v-text-field label="用户名" prepend-icon="mdi-account" v-model="user.username"
                                required></v-text-field>
                            <v-text-field label="邮箱" prepend-icon="mdi-email" v-model="user.email" type="email"
                                required></v-text-field>
                            <v-text-field label="密码" prepend-icon="mdi-lock" v-model="user.password" type="password"
                                required></v-text-field>
                            <v-text-field label="确认密码" prepend-icon="mdi-lock-check" v-model="passwordConfirm"
                                type="password" required></v-text-field>
                            <v-row no-gutters>
                                <v-col cols="9">
                                    <v-text-field label="验证码" prepend-icon="mdi-shield-key" type="text"
                                        v-model="captchaValue" required></v-text-field>
                                </v-col>
                                <v-col cols="3">
                                    <div class="captcha-container">
                                        <img :src="captchaImageUrl" @click="refreshCaptcha" />
                                    </div>
                                </v-col>
                            </v-row>
                        </v-form>
                    </v-card-text>
                    <v-card-actions>
                        <v-spacer></v-spacer>
                        <v-btn color="primary" @click="register">注册</v-btn>
                    </v-card-actions>
                    <v-card-actions>
                        <v-spacer></v-spacer>
                        <v-btn text color="green" @click="openLoginPage" @click.middle.prevent="openLoginPageInNewTab">立即登录
                            <v-icon icon="mdi-open-in-new" right />
                        </v-btn>
                    </v-card-actions>
                    <v-alert v-if="message" :type="messageType" class="mt-4">
                        {{ message }}
                    </v-alert>
                </v-card>
            </v-col>
        </v-row>
    </v-container>
</template>

  
<script>
import axios from 'axios';
import appConfig from '@/config/appConfig.json';

export default {
    data() {
        return {
            user: {
                username: '',
                email: '',
                password: ''
            },
            passwordConfirm: '',
            message: '',
            captchaKey: '',
            captchaValue: '',
            captchaImageUrl: '',
        };
    },
    methods: {
        async register() {
            if (this.user.password !== this.passwordConfirm) {
                this.message = '密码不匹配';
                this.messageType = 'error';
                return;
            }
            try {
                const formData = new URLSearchParams();
                Object.keys(this.user).forEach(key => {
                    formData.append(key, this.user[key]);
                });
                formData.append('captcha_key', this.captchaKey);
                formData.append('captcha_value', this.captchaValue);

                const response = await axios.post(`${appConfig.backendUrl}/user/register_user`, formData, {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    withCredentials: true
                });

                if (response.data.success) {
                    this.message = '注册成功';
                    this.messageType = 'success';  // 设置消息类型为成功
                    setTimeout(() => this.$router.push('/'), 2000);
                } else {
                    this.message = response.data.message || '注册失败，请重试';
                    this.messageType = 'error';  // 设置消息类型为错误
                }
            } catch (error) {
                console.error('注册失败:', error);
                this.message = '注册失败，请重试';
                this.messageType = 'error';
            }
        },
        openLoginPage() {
            this.$router.push({ name: 'LoginPage' });
        },
        openLoginPageInNewTab() {
            const routeData = this.$router.resolve({ name: 'LoginPage' });
            window.open(routeData.href, '_blank');
        },
        async refreshCaptcha() {
            try {
                const response = await axios.get(`${appConfig.backendUrl}/user/generate_captcha`);
                this.captchaKey = response.data.key;
                this.captchaImageUrl = `${appConfig.backendUrl}${response.data.image_url}`;
            } catch (error) {
                console.error('获取验证码失败：', error);
            }
        },
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '注册';
        });
        this.refreshCaptcha();
    },
};
</script>
  
<style scoped>
.v-btn {
    font-size: 17px;
}
</style>
  