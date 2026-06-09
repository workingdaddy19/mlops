// ─── Auth ─────────────────────────────────────────────────────────────────
const Auth = {
  getToken() { return localStorage.getItem('token'); },
  setToken(t) { localStorage.setItem('token', t); },
  clear() { localStorage.removeItem('token'); localStorage.removeItem('user'); },
  isLoggedIn() { return !!this.getToken(); },
  getUser() { return JSON.parse(localStorage.getItem('user') || 'null'); },
  setUser(u) { localStorage.setItem('user', JSON.stringify(u)); },
};

// ─── API fetch ────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const token = Auth.getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) { logout(); return null; }
  return res;
}

function logout() {
  Auth.clear();
  window.location.href = '/login';
}

// ─── Sidebar toggle ───────────────────────────────────────────────────────
function initSidebar() {
  const btn = document.getElementById('sidebarToggle');
  if (!btn) return;

  // 저장된 접힘 상태 복원
  if (localStorage.getItem('sidebarCollapsed') === '1') {
    document.body.classList.add('sidebar-collapsed');
  }

  btn.addEventListener('click', () => {
    const collapsed = document.body.classList.toggle('sidebar-collapsed');
    localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '0');
  });
}

// ─── Accordion toggle ─────────────────────────────────────────────────────
function toggleGroup(id) {
  const grp = document.getElementById(id);
  if (!grp) return;
  const isOpen = grp.classList.toggle('open');
  localStorage.setItem('menu_' + id, isOpen ? '1' : '0');
}

function restoreAccordionStates() {
  const groups = ['grp-data', 'grp-analysis', 'grp-models', 'grp-mgmt'];
  groups.forEach(id => {
    const grp = document.getElementById(id);
    if (!grp) return;
    const saved = localStorage.getItem('menu_' + id);
    if (saved !== null) {
      const isOpen = saved === '1';
      grp.classList.toggle('open', isOpen);
    }
  });
}

// ─── Admin 메뉴 표시 ─────────────────────────────────────────────────────
function initAdminMenu() {
  const user = Auth.getUser();
  if (user && user.role === 'admin') {
    const mgmt = document.getElementById('grp-mgmt');
    if (mgmt) mgmt.style.display = '';
  }
}

// ─── Feature Permissions ─────────────────────────────────────────────────
window._myPermissions = null;

async function loadMyPermissions() {
  if (window._myPermissions !== null) return window._myPermissions;
  try {
    const res = await apiFetch('/api/auth/me/permissions');
    window._myPermissions = (res && res.ok) ? await res.json() : [];
  } catch {
    window._myPermissions = [];
  }
  return window._myPermissions;
}

function hasPermission(feature) {
  return (window._myPermissions || []).includes(feature);
}

// ─── DOMContentLoaded ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (window.location.pathname === '/login') return;

  if (!Auth.isLoggedIn()) {
    window.location.href = '/login';
    return;
  }

  const user = Auth.getUser();
  const el = document.getElementById('nav-username');
  if (el && user) el.textContent = user.name || user.username;

  initSidebar();
  restoreAccordionStates();
  initAdminMenu();
});
