// 认证管理模块
const Auth = {
    // 检查用户登录状态
    async checkAuth() {
        try {
            const response = await fetch('/api/auth/me');
            if (response.ok) {
                const data = await response.json();
                this.showMainApp(data.data);
                return true;
            }
        } catch (error) {
            console.error('Auth check failed:', error);
        }
        this.showLoginPage();
        return false;
    },

    // 显示登录页面
    showLoginPage() {
        document.getElementById('loginPage').classList.remove('hidden');
        document.getElementById('registerPage').classList.add('hidden');
        document.getElementById('mainApp').classList.add('hidden');
    },

    // 显示注册页面
    showRegisterPage() {
        document.getElementById('loginPage').classList.add('hidden');
        document.getElementById('registerPage').classList.remove('hidden');
        document.getElementById('mainApp').classList.add('hidden');
    },

    // 显示主应用
    showMainApp(user) {
        document.getElementById('loginPage').classList.add('hidden');
        document.getElementById('registerPage').classList.add('hidden');
        document.getElementById('mainApp').classList.remove('hidden');

        // 更新用户信息显示
        document.getElementById('userSection').classList.remove('hidden');
        document.getElementById('userSection').classList.add('flex');
        document.getElementById('usernameDisplay').textContent = user.username;
    },

    // 登录
    async login(username, password) {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
                credentials: 'include'
            });

            const data = await response.json();

            if (response.ok && data.code === 0) {
                this.showMainApp(data.data.user);
                return { success: true };
            }

            return { success: false, message: data.detail || data.message || '登录失败' };
        } catch (error) {
            console.error('Login error:', error);
            return { success: false, message: '网络错误，请稍后重试' };
        }
    },

    // 注册
    async register(username, email, password) {
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password }),
                credentials: 'include'
            });

            const data = await response.json();

            if (response.ok && data.code === 0) {
                return { success: true };
            }

            return { success: false, message: data.detail || data.message || '注册失败' };
        } catch (error) {
            console.error('Register error:', error);
            return { success: false, message: '网络错误，请稍后重试' };
        }
    },

    // 登出
    async logout() {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                credentials: 'include'
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
        this.showLoginPage();
    }
};

// 登录表单处理
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');

    const result = await Auth.login(username, password);

    if (result.success) {
        errorDiv.classList.add('hidden');
        document.getElementById('loginUsername').value = '';
        document.getElementById('loginPassword').value = '';
    } else {
        errorDiv.textContent = result.message;
        errorDiv.classList.remove('hidden');
    }
});

// 注册表单处理
document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('registerUsername').value.trim();
    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = document.getElementById('registerConfirmPassword').value;
    const errorDiv = document.getElementById('registerError');

    if (password !== confirmPassword) {
        errorDiv.textContent = '两次输入的密码不一致';
        errorDiv.classList.remove('hidden');
        return;
    }

    const result = await Auth.register(username, email, password);

    if (result.success) {
        errorDiv.classList.add('hidden');
        alert('注册成功！请登录');
        Auth.showLoginPage();
    } else {
        errorDiv.textContent = result.message;
        errorDiv.classList.remove('hidden');
    }
});

// 页面切换
document.getElementById('showRegisterBtn').addEventListener('click', (e) => {
    e.preventDefault();
    Auth.showRegisterPage();
});

document.getElementById('showLoginBtn').addEventListener('click', (e) => {
    e.preventDefault();
    Auth.showLoginPage();
});

// 登出按钮
document.getElementById('logoutBtn').addEventListener('click', () => {
    if (confirm('确定要登出吗？')) {
        Auth.logout();
    }
});

// 初始化认证检查
document.addEventListener('DOMContentLoaded', () => {
    Auth.checkAuth();
});
