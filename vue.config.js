const { defineConfig } = require('@vue/cli-service');
const appConfig = require('./src/config/appConfig.json');

module.exports = defineConfig({
  transpileDependencies: true,
  publicPath: appConfig.build.publicPath,
  assetsDir: appConfig.build.assetsDir,
  devServer: {
    host: appConfig.devServer.host,
    port: appConfig.devServer.port,
    allowedHosts: appConfig.devServer.allowedHosts,
  },
});
