<template>
    <v-container class="fill-height" fluid>
        <v-row align="center" justify="center">
            <v-col cols="12" sm="8" md="4">
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
                    <v-alert v-if="message" type="error" class="mt-4">{{ message }}</v-alert>
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
            user: {
                username: '',
                email: '',
                password: ''
            },
            passwordConfirm: '',
            message: ''
        };
    },
    methods: {
        async register() {
            if (this.user.password !== this.passwordConfirm) {
                this.message = '密码不匹配';
                return;
            }
            try {
                const response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/register_user`, this.user, {
                    withCredentials: true
                });

                if (response.data.success) {
                    this.message = '注册成功';
                    setTimeout(() => this.$router.push('/'), 2000); // 2秒后跳转到登录页面
                } else {
                    this.message = response.data.message || '注册失败，请重试';
                }
            } catch (error) {
                console.error('注册失败:', error);
                this.message = '注册失败，请重试';
            }
        },
        openLoginPage() {
            this.$router.push({ name: 'LoginPage' });
        },
        openLoginPageInNewTab() {
            const routeData = this.$router.resolve({ name: 'LoginPage' });
            window.open(routeData.href, '_blank');
        },
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '注册';
        });
    },
};
</script>
  
<style scoped>
.v-btn {
    font-size: 17px;
}
</style>
  