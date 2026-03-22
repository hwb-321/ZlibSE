<template>
  <v-app>
    <v-app-bar color="primary" dense v-if="shouldShowAppBar">
      <v-spacer></v-spacer>
      <router-link to="/" class="toolbar-title-link">
        <v-toolbar-title>ZlibSE</v-toolbar-title>
      </router-link>
      <v-spacer></v-spacer>
      <v-spacer></v-spacer>
      <template v-if="isLoggedIn">
        <v-btn text to="/personal-center">个人中心</v-btn>
        <v-btn text @click="logout">退出登录</v-btn>
      </template>
      <v-btn v-else text to="/login">登录</v-btn>
    </v-app-bar>

    <v-container style="height: 100vh;">
      <router-view style="padding-top: 60px;"></router-view>
    </v-container>
  </v-app>
</template>

<script>
import { authState, clearAccessToken } from '@/utils/auth';

export default {
  name: 'App',
  data() {
    return {
      authState,
    };
  },
  computed: {
    // 根据当前路由决定是否显示app bar
    shouldShowAppBar() {
      // 这里的逻辑可能根据你的路由结构有所不同
      // 假设 'login' 和 'register' 是登录和注册路由的名称
      const excludedRoutes = ['LoginPage', 'RegisterPage', 'EpubReaderPage'];
      return !excludedRoutes.includes(this.$route.name);
    },
    isLoggedIn() {
      return Boolean(this.authState.accessToken);
    }
  },
  methods: {
    logout() {
      clearAccessToken();
      this.$router.push('/');
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
}

.toolbar-title-link {
  text-decoration: none;
  color: inherit;
}
</style>
