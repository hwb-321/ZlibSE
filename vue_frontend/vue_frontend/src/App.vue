<template>
  <v-app>
    <v-app-bar color="primary" dense v-if="shouldShowAppBar">
      <v-spacer></v-spacer>
      <router-link to="/home" class="toolbar-title-link">
        <v-toolbar-title>ZlibSE</v-toolbar-title>
      </router-link>
      <v-spacer></v-spacer>
      <v-spacer></v-spacer>
      <v-btn text to="/personal-center">个人中心</v-btn>
      <v-btn text @click="logout">退出登录</v-btn>
    </v-app-bar>

    <router-view></router-view>
  </v-app>
</template>

<script>
import axios from 'axios';

export default {
  name: 'App',
  computed: {
    // 根据当前路由决定是否显示app bar
    shouldShowAppBar() {
      // 这里的逻辑可能根据你的路由结构有所不同
      // 假设 'login' 和 'register' 是登录和注册路由的名称
      const excludedRoutes = ['LoginPage', 'RegisterPage'];
      return !excludedRoutes.includes(this.$route.name);
    }
  },
  methods: {
    async logout() {
      try {
        const response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/logout_user`, {}, { withCredentials: true });
        if (response.data.success) {
          this.$router.push('/');
        } else {
          console.error('Logout failed:', response.data.error);
        }
      } catch (error) {
        console.error('Logout error:', error);
      }
    },
  },
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}

.toolbar-title-link {
  text-decoration: none;
  /* 移除链接下划线 */
  color: inherit;
  /* 使用v-app-bar设置的颜色 */
}
</style>
