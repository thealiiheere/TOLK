// TOLK Platform Main Application Core
const State = {
    user: null,
    token: localStorage.getItem('tolk_token') || null,
    currentScreen: 'landing', // 'landing', 'student', 'tutor', 'admin'
    demoUsers: []
};

// Initialize app on DOM ready
document.addEventListener('DOMContentLoaded', async () => {
    await initTelegramWebApp();
    await loadDemoUsers();
    await checkAuth();
    setupGlobalEvents();
});

// Telegram WebApp helper & Haptic Feedback
function tgHaptic(type = 'light') {
    if (window.Telegram?.WebApp?.HapticFeedback) {
        if (type === 'success' || type === 'error' || type === 'warning') {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
        } else {
            window.Telegram.WebApp.HapticFeedback.impactOccurred(type);
        }
    }
}

async function initTelegramWebApp() {
    if (window.Telegram && window.Telegram.WebApp) {
        const tg = window.Telegram.WebApp;
        try {
            tg.ready();
            tg.expand();
            if (tg.setHeaderColor) tg.setHeaderColor('#FFFFFF');
            if (tg.setBackgroundColor) tg.setBackgroundColor('#F8F9FA');
            if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();

            // Auto-login if opened inside Telegram and user data is available
            const tgUser = tg.initDataUnsafe?.user;
            if (tgUser && !State.token) {
                console.log("Authenticating Telegram User:", tgUser);
                const res = await fetch('/api/auth/telegram-webapp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: tgUser.id,
                        first_name: tgUser.first_name || '',
                        last_name: tgUser.last_name || '',
                        username: tgUser.username || null
                    })
                });
                const data = await res.json();
                if (res.ok && data.token) {
                    State.token = data.token;
                    State.user = data.user;
                    localStorage.setItem('tolk_token', data.token);
                    tgHaptic('success');
                }
            }
            console.log("Telegram WebApp initialized successfully");
        } catch (e) {
            console.log("Telegram WebApp context notice:", e);
        }
    }
}

// Global API Fetch helper with Auth headers
async function apiFetch(endpoint, options = {}) {
    const headers = options.headers || {};
    if (State.token) {
        headers['Authorization'] = `Bearer ${State.token}`;
        headers['X-Auth-Token'] = State.token;
    }
    
    // If body is FormData, do not set Content-Type so browser sets boundary
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    try {
        const response = await fetch(endpoint, { ...options, headers });
        if (response.status === 401) {
            // Unauthorized
            logoutUser(false);
            showToast("Сессия истекла. Пожалуйста, войдите снова.", "warning");
            throw new Error("Unauthorized");
        }
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || data.message || "Ошибка сервера");
        }
        return data;
    } catch (err) {
        console.error(`API Error on ${endpoint}:`, err);
        throw err;
    }
}

// Load demo users for Quick Switcher
async function loadDemoUsers() {
    try {
        const res = await fetch('/api/auth/demo-users');
        const data = await res.json();
        State.demoUsers = data.demo_users || [];
        renderDemoUsersList();
    } catch (e) {
        console.error("Failed to load demo accounts", e);
    }
}

// Check current user session
async function checkAuth() {
    if (!State.token) {
        renderHeader();
        navigateTo('landing');
        return;
    }

    try {
        const data = await apiFetch('/api/auth/me');
        State.user = data.user;
        renderHeader();
        // Route to corresponding role screen
        if (State.user.role === 'admin') {
            navigateTo('admin');
        } else if (State.user.role === 'tutor') {
            navigateTo('tutor');
        } else {
            navigateTo('student');
        }
    } catch (e) {
        logoutUser(false);
    }
}

// Quick demo login
async function loginDemoUser(userId) {
    try {
        const res = await fetch('/api/auth/demo-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Ошибка входа");

        State.token = data.token;
        State.user = data.user;
        localStorage.setItem('tolk_token', data.token);

        closeModal('demoSwitchModal');
        closeModal('authModal');
        renderHeader();

        showToast(`Вход выполнен: ${data.user.full_name} (${getRoleBadgeText(data.user.role)})`, "success");

        if (data.user.role === 'admin') {
            navigateTo('admin');
        } else if (data.user.role === 'tutor') {
            navigateTo('tutor');
        } else {
            navigateTo('student');
        }
    } catch (err) {
        showToast(err.message, "danger");
    }
}

// Phone login or registration
async function loginWithPhone(phone, fullName = "", telegramUsername = "") {
    try {
        const res = await fetch('/api/auth/login-phone', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                phone: phone,
                full_name: fullName,
                telegram_username: telegramUsername
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Ошибка входа");

        State.token = data.token;
        State.user = data.user;
        localStorage.setItem('tolk_token', data.token);

        closeModal('authModal');
        renderHeader();

        showToast(`Добро пожаловать, ${data.user.full_name}!`, "success");

        if (data.user.role === 'admin') {
            navigateTo('admin');
        } else if (data.user.role === 'tutor') {
            navigateTo('tutor');
        } else {
            navigateTo('student');
        }
    } catch (err) {
        showToast(err.message, "danger");
    }
}

// Logout
async function logoutUser(notify = true) {
    try {
        if (State.token) {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${State.token}` }
            });
        }
    } catch (e) {}

    State.token = null;
    State.user = null;
    localStorage.removeItem('tolk_token');
    renderHeader();
    navigateTo('landing');
    if (notify) showToast("Вы вышли из системы", "info");
}

// Navigation between screens
function navigateTo(screen) {
    State.currentScreen = screen;

    // Screens
    const screens = ['landing', 'student', 'tutor', 'admin'];
    screens.forEach(s => {
        const el = document.getElementById(`screen-${s}`);
        if (el) el.classList.add('hidden');
    });

    const activeEl = document.getElementById(`screen-${screen}`);
    if (activeEl) {
        activeEl.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    renderHeader();

    // Trigger screen-specific initializers
    if (screen === 'landing' && window.Landing) window.Landing.init();
    if (screen === 'student' && window.StudentCabinet) window.StudentCabinet.load();
    if (screen === 'tutor' && window.TutorCabinet) window.TutorCabinet.load();
    if (screen === 'admin' && window.AdminPanel) window.AdminPanel.load();
}

// Helpers for role text and colors
function getRoleBadgeText(role) {
    if (role === 'admin') return 'Администратор';
    if (role === 'tutor') return 'Тьютор';
    return 'Ученик';
}

function getRoleBadgeClass(role) {
    if (role === 'admin') return 'bg-purple-100 text-purple-800 border border-purple-200';
    if (role === 'tutor') return 'bg-blue-100 text-blue-800 border border-blue-200';
    return 'bg-emerald-100 text-emerald-800 border border-emerald-200';
}

// Header rendering
function renderHeader() {
    const userControls = document.getElementById('header-user-controls');
    const navLinks = document.getElementById('header-nav-links');
    if (!userControls) return;

    if (!State.user) {
        userControls.innerHTML = `
            <button onclick="openModal('demoSwitchModal')" class="btn-secondary text-xs sm:text-sm py-1.5 px-3">
                <span class="inline-block w-2 h-2 rounded-full bg-orange-500 animate-ping"></span>
                Быстрый демо-вход
            </button>
            <button onclick="openModal('authModal')" class="btn-primary text-xs sm:text-sm py-1.5 px-3">
                Войти / Записаться
            </button>
        `;
        if (navLinks) {
            navLinks.innerHTML = `
                <a href="#about" onclick="navigateTo('landing')" class="text-gray-600 hover:text-orange-600 text-sm font-medium">О платформе</a>
                <a href="#tariffs" onclick="navigateTo('landing')" class="text-gray-600 hover:text-orange-600 text-sm font-medium">Тарифы</a>
            `;
        }
    } else {
        const u = State.user;
        let roleScreenButton = '';
        if (u.role === 'student') {
            roleScreenButton = `<button onclick="navigateTo('student')" class="text-sm font-semibold text-gray-700 hover:text-orange-600 px-2 py-1 rounded">Мой Кабинет</button>`;
        } else if (u.role === 'tutor') {
            roleScreenButton = `<button onclick="navigateTo('tutor')" class="text-sm font-semibold text-gray-700 hover:text-orange-600 px-2 py-1 rounded">Кабинет Тьютора</button>`;
        } else if (u.role === 'admin') {
            roleScreenButton = `<button onclick="navigateTo('admin')" class="text-sm font-semibold text-gray-700 hover:text-orange-600 px-2 py-1 rounded">Админка</button>`;
        }

        if (navLinks) {
            navLinks.innerHTML = `
                <button onclick="navigateTo('landing')" class="text-sm font-medium text-gray-600 hover:text-orange-600">Главная</button>
                ${roleScreenButton}
            `;
        }

        userControls.innerHTML = `
            <div class="flex items-center gap-2">
                <button onclick="openModal('demoSwitchModal')" class="text-xs bg-orange-50 text-orange-700 border border-orange-200 px-2.5 py-1.5 rounded-lg hover:bg-orange-100 font-medium hidden md:inline-flex items-center gap-1">
                    <span>Сменить аккаунт</span>
                </button>
                <div class="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-2.5 py-1">
                    <div class="text-left text-xs">
                        <div class="font-bold text-gray-900 leading-tight">${u.full_name}</div>
                        <span class="inline-block px-1.5 py-0.2 rounded text-[10px] font-semibold ${getRoleBadgeClass(u.role)}">
                            ${getRoleBadgeText(u.role)}
                        </span>
                    </div>
                    <button onclick="logoutUser()" title="Выйти" class="text-gray-400 hover:text-red-500 p-1 rounded transition">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
                    </button>
                </div>
            </div>
        `;
    }
}

// Render Demo Users modal list
function renderDemoUsersList() {
    const container = document.getElementById('demo-users-list');
    if (!container) return;

    if (!State.demoUsers || State.demoUsers.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">Загрузка аккаунтов...</p>';
        return;
    }

    let html = '';
    
    // Group by roles
    const admins = State.demoUsers.filter(u => u.role === 'admin');
    const tutors = State.demoUsers.filter(u => u.role === 'tutor');
    const students = State.demoUsers.filter(u => u.role === 'student');

    html += `<div class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Администратор</div>`;
    admins.forEach(u => {
        html += demoUserCard(u, 'bg-purple-50 hover:bg-purple-100 border-purple-200');
    });

    html += `<div class="text-xs font-bold text-gray-400 uppercase tracking-wider mt-4 mb-2">Тьюторы (Преподаватели)</div>`;
    tutors.forEach(u => {
        html += demoUserCard(u, 'bg-blue-50 hover:bg-blue-100 border-blue-200');
    });

    html += `<div class="text-xs font-bold text-gray-400 uppercase tracking-wider mt-4 mb-2">Ученики (Тестовая группа + демо)</div>`;
    students.forEach(u => {
        let strikeText = '';
        if (u.strikes !== null && u.strikes !== undefined) {
            if (u.strikes >= 3) strikeText = `<span class="bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">🔴 3 страйка (Блок)</span>`;
            else if (u.strikes === 2) strikeText = `<span class="bg-amber-500 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">⚠️ 2 страйка</span>`;
            else if (u.strikes === 1) strikeText = `<span class="bg-amber-400 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">⚠️ 1 страйк</span>`;
            else strikeText = `<span class="bg-emerald-500 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">🟢 0 страйков</span>`;
        } else {
            strikeText = `<span class="bg-gray-200 text-gray-700 text-[10px] px-1.5 py-0.5 rounded">Без группы</span>`;
        }
        html += demoUserCard(u, 'bg-gray-50 hover:bg-orange-50 border-gray-200 hover:border-orange-300', strikeText);
    });

    container.innerHTML = html;
}

function demoUserCard(u, colorClasses, extraBadge = '') {
    return `
        <div onclick="loginDemoUser(${u.id})" class="cursor-pointer border rounded-xl p-3 mb-2 transition flex items-center justify-between ${colorClasses}">
            <div>
                <div class="font-semibold text-sm text-gray-900 flex items-center gap-2">
                    ${u.full_name}
                    ${extraBadge}
                </div>
                <div class="text-xs text-gray-500 flex items-center gap-2">
                    <span>${u.phone}</span>
                    <span>•</span>
                    <span>${u.telegram_username || '@user'}</span>
                    ${u.group_name ? `<span class="text-xs text-orange-600 truncate max-w-[200px]">• ${u.group_name}</span>` : ''}
                </div>
            </div>
            <div class="text-xs font-semibold text-orange-600">
                Войти →
            </div>
        </div>
    `;
}

// Global modal helpers
function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove('hidden');
        el.classList.add('flex');
    }
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.add('hidden');
        el.classList.remove('flex');
    }
}

// Global event listeners (forms, clicks outside)
function setupGlobalEvents() {
    // Phone auth form
    const authForm = document.getElementById('phone-auth-form');
    if (authForm) {
        authForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const phone = document.getElementById('auth-phone').value;
            const name = document.getElementById('auth-name').value;
            const tg = document.getElementById('auth-telegram').value;
            loginWithPhone(phone, name, tg);
        });
    }

    // Close modals on backdrop click
    document.querySelectorAll('.modal-backdrop').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal.id);
            }
        });
    });
}

// Toast notification helper
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const bgColors = {
        success: 'bg-emerald-600 text-white',
        danger: 'bg-red-600 text-white',
        warning: 'bg-amber-600 text-white',
        info: 'bg-gray-800 text-white'
    };

    toast.className = `${bgColors[type] || bgColors.info} px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center justify-between gap-3 transform transition-all duration-300 translate-y-2 opacity-0`;
    toast.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" class="opacity-75 hover:opacity-100">&times;</button>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    setTimeout(() => {
        toast.classList.add('translate-y-2', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
