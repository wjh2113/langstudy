// Every page has its own address, so the back button works and reports can be linked.
import { createRouter, createWebHistory } from 'vue-router'
import { stop } from './lib/audio'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./views/HomeView.vue') },
    { path: '/course/:id', name: 'course', component: () => import('./views/CoursePage.vue') },
    { path: '/practice/:id', name: 'practice', component: () => import('./views/PracticePage.vue'), meta: { bare: true } },
    { path: '/report/:id', name: 'report', component: () => import('./views/ReportPage.vue') },
    { path: '/review', name: 'review', component: () => import('./views/ReviewView.vue') },
    { path: '/accent', name: 'accent', component: () => import('./views/AccentQuizView.vue') },
    { path: '/history', name: 'history', component: () => import('./views/HistoryView.vue') },
    { path: '/notes', name: 'notes', component: () => import('./views/NotesListView.vue') },
    { path: '/notes/:id', name: 'note', component: () => import('./views/NotesDetailView.vue'), meta: { bare: true } },
    { path: '/admin', name: 'admin', component: () => import('./views/AdminView.vue'), meta: { admin: true } },
    { path: '/account', name: 'account', component: () => import('./views/AccountView.vue') },
    // read-only report anyone with the link can open (no login)
    { path: '/share/:token', name: 'share', component: () => import('./views/SharePage.vue'), meta: { public: true } },
    { path: '/:rest(.*)*', name: 'notfound', component: () => import('./views/NotFound.vue') },
  ],
  scrollBehavior: (_to, _from, saved) => saved || { top: 0 },
})

router.beforeEach(() => {
  stop() // leaving a page stops whatever is being read aloud
})
