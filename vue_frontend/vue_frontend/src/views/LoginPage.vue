<template>
    <div class="login-container">
        <h2>Login</h2>
        <form @submit.prevent="submitLogin">
            <div>
                <label for="username">Username:</label>
                <input id="username" v-model="username" type="text" required>
            </div>
            <div>
                <label for="password">Password:</label>
                <input id="password" v-model="password" type="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        <div v-if="errorMessage">{{ errorMessage }}</div>
    </div>
</template>
  
<script>
import axios from 'axios';

export default {
    data() {
        return {
            username: '',
            password: '',
            errorMessage: ''
        };
    },
    methods: {
        async submitLogin() {
            try {
                const formData = new URLSearchParams();
                formData.append('username', this.username);
                formData.append('password', this.password);

                const response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/login_user/`, formData, {
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
    }
};
</script>
  
<style scoped>
.login-container {
    margin: 2px;
}
</style>
  