export interface NavItem { to: string; name: string; label: string; icon: string; admin?: boolean; badge?: 'due' }

/** Main navigation, shared by the sidebar and the avatar menu. */
export const NAV: NavItem[] = [
  { to: '/', name: 'home', label: '首页', icon: 'home' },
  { to: '/review', name: 'review', label: '复习', icon: 'cards', badge: 'due' },
  { to: '/accent', name: 'accent', label: '口音听辨', icon: 'ear' },
  { to: '/history', name: 'history', label: '练习历史', icon: 'clock' },
  { to: '/notes', name: 'notes', label: '学习笔记', icon: 'book' },
  { to: '/admin', name: 'admin', label: '用户与邀请', icon: 'users', admin: true },
  { to: '/account', name: 'account', label: '账号设置', icon: 'settings' },
]
