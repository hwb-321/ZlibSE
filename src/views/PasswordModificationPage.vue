<template>
    <v-container>
        <v-row justify="center">
            <v-col cols="12" md="6">
                <v-card>
                    <v-card-title class="text-h5">修改密码</v-card-title>
                    <v-card-text>
                        <v-form ref="form" v-model="valid" lazy-validation>
                            <v-text-field v-model="passwords.current" label="当前密码" type="password" required></v-text-field>
                            <v-text-field v-model="passwords.new" :rules="passwordRules" label="新密码" type="password"
                                required></v-text-field>
                            <v-text-field v-model="passwords.confirm" :rules="confirmPasswordRules" label="确认新密码"
                                type="password" required></v-text-field>
                            <v-btn :disabled="!valid" color="primary" @click="submitChangePassword">
                                修改密码
                            </v-btn>
                        </v-form>

                        <v-alert type="success" v-if="successMessage" class="mt-4" dismissible>
                            {{ successMessage }}
                        </v-alert>

                        <v-alert type="error" v-if="errorMessage" class="mt-4" dismissible>
                            {{ errorMessage }}
                        </v-alert>
                    </v-card-text>
                </v-card>
            </v-col>
        </v-row>
    </v-container>
</template>
  
<script>
import axios from 'axios';
import appConfig from '@/config/appConfig.json';
import { clearAccessToken } from '@/utils/auth';

export default {
    data() {
        return {
            valid: false,
            passwords: {
                current: '',
                new: '',
                confirm: ''
            },
            passwordRules: [
                v => !!v || '密码是必填项',
                v => v.length >= 8 || '密码长度至少为 8 个字符'
            ],
            confirmPasswordRules: [
                v => !!v || '确认密码是必填项',
                v => v === this.passwords.new || '两次输入的密码不一致'
            ],
            successMessage: '',
            errorMessage: '',
        };
    },
    methods: {
        submitChangePassword() {
            if (this.$refs.form.validate()) {
                // 构建 formData 对象
                const formData = new FormData();
                formData.append('current_password', this.passwords.current);
                formData.append('new_password', this.passwords.new);
                // 发送请求
                axios.put(`${appConfig.backendUrl}/api/users/me/password`, formData, {
                })
                    .then(response => {
                        if (response.data.success) {
                            clearAccessToken();
                            this.successMessage = '密码修改成功，请重新登录。';
                            this.errorMessage = '';
                            setTimeout(() => {
                                this.$router.push({ name: 'LoginPage' });
                            }, 1500);
                        } else {
                            this.errorMessage = response.data.message;
                            this.successMessage = '';
                        }
                    })
                    .catch(error => {
                        this.errorMessage = error.response?.data?.message || '请求失败，请重试。';
                        this.successMessage = '';
                    });
            }
        }
    }
};
</script>
  
