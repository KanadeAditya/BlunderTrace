// URL → page mapping (like React Router's <Routes>, or the app/ folder in Next.js).
import { createRouter, createWebHistory } from 'vue-router'

import GamePage from './pages/GamePage.vue'
import HomePage from './pages/HomePage.vue'
import ReportPage from './pages/ReportPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomePage },
    // One URL for both the Analysing screen and the finished report (docs/PLAN.md, stage 2).
    { path: '/report/:id', name: 'report', component: ReportPage, props: true },
    // ?ply=7 opens the game at that half-move (used by the report's examples).
    { path: '/report/:id/game/:gameId', name: 'game', component: GamePage, props: true },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
