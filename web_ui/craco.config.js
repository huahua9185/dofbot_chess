module.exports = {
  devServer: (devServerConfig) => {
    // Remove deprecated middleware options
    delete devServerConfig.onBeforeSetupMiddleware;
    delete devServerConfig.onAfterSetupMiddleware;

    // Use the new setupMiddlewares option
    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      return middlewares;
    };

    return devServerConfig;
  },
  webpack: {
    configure: (webpackConfig) => {
      // Suppress source map warnings for third-party modules
      webpackConfig.ignoreWarnings = [
        {
          module: /node_modules/,
          message: /Failed to parse source map/,
        },
      ];

      return webpackConfig;
    },
  },
};