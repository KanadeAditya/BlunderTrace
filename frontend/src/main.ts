// App entry point — like React's main.tsx with createRoot(...).render(<App />).
import { createApp } from 'vue'

// Self-hosted fonts (DESIGN.md §3). "full" = every variable axis of Fraunces (weight + optical size).
import '@fontsource-variable/fraunces/full.css'
import '@fontsource-variable/fraunces/full-italic.css'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '@fontsource/noto-sans-symbols-2'

import './styles/main.css'
import App from './App.vue'
import { router } from './router'

createApp(App).use(router).mount('#app')
