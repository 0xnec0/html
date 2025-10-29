const { defineConfig } = require('cypress');
const synpressPlugins = require('@synthetixio/synpress/plugins');

module.exports = defineConfig({
  userAgent: 'synpress',
  retries: {
    runMode: 0,
    openMode: 0,
  },
  screenshotsFolder: 'tests/e2e/screenshots',
  videosFolder: 'tests/e2e/videos',
  video: false,
  screenshotOnRunFailure: true,
  chromeWebSecurity: true,
  viewportWidth: 1920,
  viewportHeight: 1080,
  env: {
    coverage: false,
  },
  defaultCommandTimeout: 30000,
  pageLoadTimeout: 30000,
  requestTimeout: 30000,
  e2e: {
    testIsolation: false,
    setupNodeEvents(on, config) {
      synpressPlugins(on, config);
    },
    baseUrl: 'http://localhost:3000',
    specPattern: 'tests/e2e/specs/**/*.{js,jsx,ts,tsx}',
    supportFile: 'tests/e2e/support/e2e.js',
  },
});
