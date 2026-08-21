import { registerPlugin } from '@capacitor/core'

const ApkUpdater = registerPlugin('ApkUpdater', {
  web: {
    async downloadAndInstall(options) {
      if (options?.url) {
        window.open(options.url, '_system', 'location=yes')
      }
      return { value: 'web' }
    },
  },
})

export default ApkUpdater
