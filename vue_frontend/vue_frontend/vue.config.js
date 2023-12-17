const { defineConfig } = require('@vue/cli-service');

module.exports = defineConfig({
  transpileDependencies: true,
  publicPath: process.env.NODE_ENV === 'production'
    ? '/'  // 生产环境下的公共路径
    : '/',        // 开发环境下的公共路径
});
