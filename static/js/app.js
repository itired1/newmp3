// Main Application

class App {
    static init() {
        // Initialize utilities
        Utils.initTheme();
        Utils.initParticles();
        
        // Initialize components
        this.initPreloader();
        this.initNavigation();
        this.initSidebar();
        this.initSearch();
        this.initNotifications();
        this.initUserMenu();
        this.initThemeToggle();
        this.initDailyReward();
        this.initPageTransitions();
        this.initModals();
        
        // Load user data
        if (document.getElementById('user-avatar')) {
            this.loadUserData();
        }
        
        // Initialize service worker for PWA
        this.initServiceWorker();
        
        // Listen for online/offline status
        this.initNetworkStatus();
        
        console.log('itired application initialized');
    }
    
    static initPreloader() {
        const preloader = document.getElementById('preloader');
        if (!preloader) return;
        
        // Hide preloader when page is loaded
        window.addEventListener('load', () => {
            setTimeout(() => {
                preloader.classList.add('fade-out');
                
                setTimeout(() => {
                    preloader.style.display = 'none';
                    document.body.classList.add('loaded');
                    
                    // Add some fun effects
                    if (Math.random() > 0.5) {
                        Utils.createMusicNotes(10);
                    }
                }, 500);
            }, 1000);
        });
        
        // Show preloader for at least 1 second
        setTimeout(() => {
            preloader.classList.add('fade-out');
        }, 1000);
    }
    
    static initNavigation() {
        // Handle navigation items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (item.getAttribute('href').startsWith('#')) {
                    e.preventDefault();
                    const page = item.dataset.page;
                    this.navigateToPage(page);
                }
            });
        });
        
        // Update active nav item based on current page
        this.updateActiveNav();
        
        // Handle browser back/forward
        window.addEventListener('popstate', () => {
            this.updateActiveNav();
        });
    }
    
    static navigateToPage(page) {
        // Update URL without reload
        history.pushState({ page }, '', `#${page}`);
        
        // Update active nav
        this.updateActiveNav();
        
        // Load page content
        this.loadPageContent(page);
    }
    
    static updateActiveNav() {
        const currentPage = location.hash.replace('#', '') || 'dashboard';
        
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.page === currentPage) {
                item.classList.add('active');
            }
        });
    }
    
    static async loadPageContent(page) {
        const contentArea = document.getElementById('page-content');
        if (!contentArea) return;
        
        // Add loading animation
        contentArea.innerHTML = `
            <div class="page-loading">
                <div class="loading-spinner"></div>
                <p>Загрузка...</p>
            </div>
        `;
        
        try {
            let html = '';
            
            switch (page) {
                case 'dashboard':
                    html = await this.getDashboardHTML();
                    break;
                case 'profile':
                    html = await this.getProfileHTML();
                    break;
                case 'music':
                    html = await this.getMusicHTML();
                    break;
                case 'shop':
                    html = await this.getShopHTML();
                    break;
                case 'inventory':
                    html = await this.getInventoryHTML();
                    break;
                case 'friends':
                    html = await this.getFriendsHTML();
                    break;
                case 'settings':
                    html = await this.getSettingsHTML();
                    break;
                case 'admin':
                    html = await this.getAdminHTML();
                    break;
                default:
                    html = await this.getDashboardHTML();
            }
            
            // Fade in new content
            contentArea.style.opacity = '0';
            contentArea.innerHTML = html;
            
            setTimeout(() => {
                contentArea.style.opacity = '1';
                
                // Initialize page-specific components
                this.initPageComponents(page);
            }, 300);
            
        } catch (error) {
            console.error('Error loading page:', error);
            contentArea.innerHTML = `
                <div class="error-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Ошибка загрузки</h3>
                    <p>Не удалось загрузить страницу. Пожалуйста, попробуйте позже.</p>
                    <button class="btn btn-primary" onclick="App.navigateToPage('dashboard')">
                        Вернуться на главную
                    </button>
                </div>
            `;
        }
    }
    
    static async getDashboardHTML() {
        // In a real app, this would fetch from server
        return `
            <div class="dashboard">
                <div class="dashboard-header">
                    <h1>Добро пожаловать в itired! 🎵</h1>
                    <p>Ваш персональный музыкальный сервис</p>
                </div>
                
                <div class="dashboard-stats grid grid-4">
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-headphones"></i>
                        </div>
                        <div class="stat-info">
                            <h3 id="tracks-listened">0</h3>
                            <p>Треков прослушано</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-clock"></i>
                        </div>
                        <div class="stat-info">
                            <h3 id="minutes-listened">0</h3>
                            <p>Минут музыки</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-coins"></i>
                        </div>
                        <div class="stat-info">
                            <h3 id="dashboard-balance">0</h3>
                            <p>Монет в кошельке</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-trophy"></i>
                        </div>
                        <div class="stat-info">
                            <h3 id="daily-streak">0</h3>
                            <p>Дней подряд</p>
                        </div>
                    </div>
                </div>
                
                <div class="dashboard-content grid grid-2">
                    <div class="card">
                        <div class="card-header">
                            <h2 class="card-title">Рекомендации</h2>
                            <button class="btn btn-sm btn-outline" id="refresh-recommendations">
                                <i class="fas fa-redo"></i>
                            </button>
                        </div>
                        <div class="card-body">
                            <div id="recommendations-list" class="recommendations-list">
                                <!-- Recommendations will be loaded here -->
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <h2 class="card-title">Недавние треки</h2>
                        </div>
                        <div class="card-body">
                            <div id="recent-tracks" class="tracks-list">
                                <!-- Recent tracks will be loaded here -->
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card mt-4">
                    <div class="card-header">
                        <h2 class="card-title">Быстрый доступ</h2>
                    </div>
                    <div class="card-body">
                        <div class="quick-actions grid grid-4">
                            <a href="#shop" class="quick-action">
                                <div class="action-icon">
                                    <i class="fas fa-store"></i>
                                </div>
                                <span>Магазин</span>
                            </a>
                            
                            <a href="#music" class="quick-action">
                                <div class="action-icon">
                                    <i class="fas fa-headphones"></i>
                                </div>
                                <span>Моя музыка</span>
                            </a>
                            
                            <a href="#friends" class="quick-action">
                                <div class="action-icon">
                                    <i class="fas fa-users"></i>
                                </div>
                                <span>Друзья</span>
                            </a>
                            
                            <button class="quick-action" id="quick-settings">
                                <div class="action-icon">
                                    <i class="fas fa-cog"></i>
                                </div>
                                <span>Настройки</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    static async getProfileHTML() {
        return `
            <div class="profile-page">
                <div class="profile-header">
                    <h1>Мой профиль</h1>
                    <p>Управляйте вашим профилем и настройками</p>
                </div>
                
                <div class="grid grid-2 gap-4">
                    <div class="card">
                        <div class="card-header">
                            <h2 class="card-title">Информация профиля</h2>
                        </div>
                        <div class="card-body">
                            <form id="profile-form">
                                <div class="form-group">
                                    <label class="form-label">Аватар</label>
                                    <div class="avatar-upload">
                                        <div class="avatar-preview" id="avatar-preview">
                                            <img src="" alt="Avatar">
                                        </div>
                                        <div class="avatar-upload-controls">
                                            <button type="button" class="btn btn-sm btn-outline" id="upload-avatar-btn">
                                                <i class="fas fa-upload"></i> Загрузить
                                            </button>
                                            <input type="file" id="avatar-input" accept="image/*" style="display: none;">
                                            <button type="button" class="btn btn-sm btn-outline" id="remove-avatar-btn">
                                                <i class="fas fa-trash"></i> Удалить
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="form-group">
                                    <label class="form-label">Имя пользователя</label>
                                    <input type="text" class="form-control" id="profile-username" readonly>
                                </div>
                                
                                <div class="form-group">
                                    <label class="form-label">Отображаемое имя</label>
                                    <input type="text" class="form-control" id="profile-display-name" 
                                           placeholder="Введите отображаемое имя">
                                </div>
                                
                                <div class="form-group">
                                    <label class="form-label">О себе</label>
                                    <textarea class="form-control" id="profile-bio" 
                                              rows="3" placeholder="Расскажите о себе"></textarea>
                                </div>
                                
                                <div class="form-group">
                                    <button type="submit" class="btn btn-primary" id="save-profile-btn">
                                        <i class="fas fa-save"></i> Сохранить изменения
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <h2 class="card-title">Подключенные сервисы</h2>
                        </div>
                        <div class="card-body">
                            <div class="service-card" id="yandex-service">
                                <div class="service-icon">
                                    <i class="fab fa-yandex"></i>
                                </div>
                                <div class="service-info">
                                    <h4>Яндекс.Музыка</h4>
                                    <p id="yandex-status">Не подключено</p>
                                </div>
                                <button class="btn btn-sm btn-outline" id="connect-yandex-btn">
                                    Подключить
                                </button>
                            </div>
                            
                            <div class="service-card" id="vk-service">
                                <div class="service-icon">
                                    <i class="fab fa-vk"></i>
                                </div>
                                <div class="service-info">
                                    <h4>VK Музыка</h4>
                                    <p id="vk-status">Не подключено</p>
                                </div>
                                <button class="btn btn-sm btn-outline" id="connect-vk-btn">
                                    Подключить
                                </button>
                            </div>
                        </div>
                        
                        <div class="card-header mt-4">
                            <h2 class="card-title">Статистика</h2>
                        </div>
                        <div class="card-body">
                            <div class="stats-grid">
                                <div class="stat-item">
                                    <span class="stat-value" id="profile-tracks">0</span>
                                    <span class="stat-label">Треков</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-value" id="profile-minutes">0</span>
                                    <span class="stat-label">Минут</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-value" id="profile-friends">0</span>
                                    <span class="stat-label">Друзей</span>
                                </div>
                                <div class="stat-item">
                                    <span class="stat-value" id="profile-items">0</span>
                                    <span class="stat-label">Предметов</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    static initPageComponents(page) {
        switch (page) {
            case 'dashboard':
                this.initDashboard();
                break;
            case 'profile':
                this.initProfilePage();
                break;
            case 'shop':
                if (typeof Shop !== 'undefined') {
                    Shop.init();
                }
                break;
            // Add other page initializations
        }
    }
    
    static async loadUserData() {
        try {
            const profile = await API.getProfile();
            this.updateUserUI(profile);
        } catch (error) {
            console.error('Error loading user data:', error);
        }
    }
    
    static updateUserUI(profile) {
        // Update avatar
        const avatarImg = document.getElementById('avatar-img');
        const headerAvatar = document.getElementById('header-avatar');
        const avatarPreview = document.getElementById('avatar-preview');
        
        if (profile.user.avatar_url) {
            avatarImg.src = profile.user.avatar_url;
            headerAvatar.src = profile.user.avatar_url;
            if (avatarPreview) {
                avatarPreview.querySelector('img').src = profile.user.avatar_url;
            }
        }
        
        // Update username
        document.getElementById('username').textContent = profile.user.display_name || profile.user.username;
        document.getElementById('header-username').textContent = profile.user.display_name || profile.user.username;
        
        // Update email
        document.getElementById('user-email').textContent = profile.user.email;
        
        // Update profile form
        const usernameInput = document.getElementById('profile-username');
        const displayNameInput = document.getElementById('profile-display-name');
        const bioInput = document.getElementById('profile-bio');
        
        if (usernameInput) {
            usernameInput.value = profile.user.username;
            displayNameInput.value = profile.user.display_name || '';
            bioInput.value = profile.user.bio || '';
        }
        
        // Load currency balance
        this.loadCurrencyBalance();
    }
    
    static async loadCurrencyBalance() {
        try {
            const balanceData = await API.getCurrencyBalance();
            const balanceElement = document.getElementById('user-balance');
            const dashboardBalance = document.getElementById('dashboard-balance');
            
            if (balanceElement) {
                balanceElement.textContent = balanceData.balance;
            }
            
            if (dashboardBalance) {
                dashboardBalance.textContent = balanceData.balance;
            }
        } catch (error) {
            console.error('Error loading currency balance:', error);
        }
    }
    
    static initSidebar() {
        const sidebar = document.getElementById('sidebar');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const menuToggle = document.getElementById('menu-toggle');
        
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');
            });
        }
        
        if (menuToggle) {
            menuToggle.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');
            });
        }
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 991) {
                if (!sidebar.contains(e.target) && 
                    !menuToggle.contains(e.target) && 
                    !sidebar.classList.contains('collapsed')) {
                    sidebar.classList.add('collapsed');
                }
            }
        });
    }
    
    static initSearch() {
        const searchInput = document.getElementById('global-search');
        const searchResults = document.getElementById('search-results');
        
        if (!searchInput || !searchResults) return;
        
        let searchTimeout;
        
        searchInput.addEventListener('input', Utils.debounce(async (e) => {
            const query = e.target.value.trim();
            
            if (query.length < 2) {
                searchResults.classList.remove('active');
                return;
            }
            
            try {
                searchResults.innerHTML = `
                    <div class="search-loading">
                        <div class="loading-spinner sm"></div>
                        <span>Поиск...</span>
                    </div>
                `;
                searchResults.classList.add('active');
                
                const results = await API.search(query);
                
                if (!results.tracks || results.tracks.length === 0) {
                    searchResults.innerHTML = `
                        <div class="search-empty">
                            <i class="fas fa-search"></i>
                            <p>Ничего не найдено</p>
                        </div>
                    `;
                    return;
                }
                
                let html = '<div class="search-section">';
                html += '<h4>Треки</h4>';
                
                results.tracks.slice(0, 5).forEach(track => {
                    html += `
                        <div class="search-item" data-track-id="${track.id}">
                            <div class="search-item-cover">
                                <img src="${track.cover_uri || '/static/assets/images/default-cover.png'}" 
                                     alt="${track.title}">
                            </div>
                            <div class="search-item-info">
                                <div class="search-item-title">${track.title}</div>
                                <div class="search-item-artist">${track.artists.join(', ')}</div>
                            </div>
                            <button class="search-item-play" data-service="${track.service}" 
                                    data-track-id="${track.id.split('_')[1]}">
                                <i class="fas fa-play"></i>
                            </button>
                        </div>
                    `;
                });
                
                html += '</div>';
                searchResults.innerHTML = html;
                
                // Add click handlers for play buttons
                searchResults.querySelectorAll('.search-item-play').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const service = btn.dataset.service;
                        const trackId = btn.dataset.trackId;
                        
                        if (typeof Player !== 'undefined') {
                            Player.playTrack(service, trackId);
                        }
                        
                        searchResults.classList.remove('active');
                        searchInput.value = '';
                    });
                });
                
            } catch (error) {
                console.error('Search error:', error);
                searchResults.innerHTML = `
                    <div class="search-error">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>Ошибка поиска</p>
                    </div>
                `;
            }
        }, 500));
        
        // Close search results when clicking outside
        document.addEventListener('click', (e) => {
            if (!searchResults.contains(e.target) && !searchInput.contains(e.target)) {
                searchResults.classList.remove('active');
            }
        });
    }
    
    static initNotifications() {
        const notificationBtn = document.getElementById('notification-btn');
        const notificationDropdown = document.getElementById('notification-dropdown');
        
        if (!notificationBtn || !notificationDropdown) return;
        
        notificationBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            notificationDropdown.classList.toggle('active');
            
            // Mark notifications as read
            const notificationCount = document.getElementById('notification-count');
            if (notificationCount.textContent !== '0') {
                notificationCount.textContent = '0';
                notificationCount.style.display = 'none';
            }
        });
        
        // Close when clicking outside
        document.addEventListener('click', () => {
            notificationDropdown.classList.remove('active');
        });
        
        // Load notifications
        this.loadNotifications();
    }
    
    static async loadNotifications() {
        // In a real app, fetch from API
        const notifications = [
            {
                id: 1,
                type: 'reward',
                title: 'Ежедневная награда',
                message: 'Получите бонусные монеты сегодня!',
                time: '10 минут назад',
                read: false
            },
            {
                id: 2,
                type: 'friend',
                title: 'Новый друг',
                message: 'User123 добавил вас в друзья',
                time: '1 час назад',
                read: false
            },
            {
                id: 3,
                type: 'shop',
                title: 'Новые товары',
                message: 'В магазине появились новые аватары',
                time: '2 часа назад',
                read: true
            }
        ];
        
        const unreadCount = notifications.filter(n => !n.read).length;
        const notificationCount = document.getElementById('notification-count');
        const notificationDropdown = document.getElementById('notification-dropdown');
        
        if (notificationCount) {
            notificationCount.textContent = unreadCount;
            notificationCount.style.display = unreadCount > 0 ? 'flex' : 'none';
        }
        
        if (notificationDropdown) {
            let html = '<div class="notifications-header">';
            html += '<h4>Уведомления</h4>';
            html += '<button class="btn btn-sm btn-outline" id="mark-all-read">';
            html += '<i class="fas fa-check-double"></i> Прочитать все</button>';
            html += '</div>';
            
            if (notifications.length === 0) {
                html += '<div class="notifications-empty">';
                html += '<i class="fas fa-bell-slash"></i>';
                html += '<p>Нет новых уведомлений</p>';
                html += '</div>';
            } else {
                notifications.forEach(notification => {
                    html += `
                        <div class="notification-item ${notification.read ? 'read' : 'unread'}">
                            <div class="notification-icon">
                                <i class="fas fa-${this.getNotificationIcon(notification.type)}"></i>
                            </div>
                            <div class="notification-content">
                                <div class="notification-title">${notification.title}</div>
                                <div class="notification-message">${notification.message}</div>
                                <div class="notification-time">${notification.time}</div>
                            </div>
                        </div>
                    `;
                });
            }
            
            notificationDropdown.innerHTML = html;
            
            // Add handler for mark all as read
            const markAllReadBtn = document.getElementById('mark-all-read');
            if (markAllReadBtn) {
                markAllReadBtn.addEventListener('click', () => {
                    notificationCount.textContent = '0';
                    notificationCount.style.display = 'none';
                    notificationDropdown.querySelectorAll('.notification-item').forEach(item => {
                        item.classList.remove('unread');
                        item.classList.add('read');
                    });
                });
            }
        }
    }
    
    static getNotificationIcon(type) {
        const icons = {
            'reward': 'gift',
            'friend': 'user-plus',
            'shop': 'store',
            'music': 'music',
            'system': 'cog',
            'warning': 'exclamation-triangle'
        };
        return icons[type] || 'bell';
    }
    
    static initUserMenu() {
        const userMenuBtn = document.getElementById('user-menu-btn');
        const userDropdown = document.getElementById('user-dropdown-menu');
        
        if (!userMenuBtn || !userDropdown) return;
        
        userMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            userDropdown.classList.toggle('active');
        });
        
        // Close when clicking outside
        document.addEventListener('click', () => {
            userDropdown.classList.remove('active');
        });
    }
    
    static initThemeToggle() {
        const themeToggle = document.getElementById('theme-toggle');
        if (!themeToggle) return;
        
        themeToggle.addEventListener('click', () => {
            const newTheme = Utils.toggleTheme();
            Utils.toast(`Тема изменена на ${newTheme === 'dark' ? 'тёмную' : 'светлую'}`, 'success');
        });
    }
    
    static initDailyReward() {
        const dailyRewardBtn = document.getElementById('daily-reward-btn');
        if (!dailyRewardBtn) return;
        
        dailyRewardBtn.addEventListener('click', async () => {
            dailyRewardBtn.disabled = true;
            dailyRewardBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Получение...';
            
            try {
                const result = await API.claimDailyReward();
                
                if (result.success) {
                    Utils.toast(result.message, 'success');
                    
                    // Update balance
                    this.loadCurrencyBalance();
                    
                    // Show confetti
                    Utils.createConfetti(100);
                    
                    // Update button state
                    dailyRewardBtn.innerHTML = '<i class="fas fa-check"></i> Получено сегодня';
                    dailyRewardBtn.disabled = true;
                    
                    // Update progress
                    const rewardProgress = document.getElementById('reward-progress');
                    const rewardStreak = document.getElementById('reward-streak');
                    
                    if (rewardProgress && rewardStreak) {
                        const newStreak = result.consecutive_days || 1;
                        const progress = (newStreak % 7) * (100 / 7);
                        
                        rewardProgress.style.width = `${progress}%`;
                        rewardStreak.textContent = `День ${newStreak}`;
                    }
                } else {
                    Utils.toast(result.message, 'error');
                    dailyRewardBtn.disabled = false;
                    dailyRewardBtn.innerHTML = '<i class="fas fa-coins"></i> Получить награду';
                }
            } catch (error) {
                Utils.toast('Ошибка получения награды', 'error');
                dailyRewardBtn.disabled = false;
                dailyRewardBtn.innerHTML = '<i class="fas fa-coins"></i> Получить награду';
            }
        });
    }
    
    static initPageTransitions() {
        // Smooth page transitions
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a');
            if (link && link.href && link.href.startsWith(window.location.origin) && 
                !link.href.includes('#') && link.target !== '_blank') {
                e.preventDefault();
                
                // Add page transition
                document.body.style.opacity = '0.7';
                
                setTimeout(() => {
                    window.location.href = link.href;
                }, 300);
            }
        });
    }
    
    static initModals() {
        const modalOverlay = document.getElementById('modal-overlay');
        
        // Close modal when clicking overlay
        if (modalOverlay) {
            modalOverlay.addEventListener('click', () => {
                this.closeModal();
            });
        }
        
        // Close modal with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }
    
    static showModal(modalId) {
        const modal = document.getElementById(modalId);
        const modalOverlay = document.getElementById('modal-overlay');
        
        if (!modal || !modalOverlay) return;
        
        modal.classList.add('active');
        modalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    static closeModal() {
        const modals = document.querySelectorAll('.modal.active');
        const modalOverlay = document.getElementById('modal-overlay');
        
        modals.forEach(modal => {
            modal.classList.remove('active');
        });
        
        if (modalOverlay) {
            modalOverlay.classList.remove('active');
        }
        
        document.body.style.overflow = '';
    }
    
    static initDashboard() {
        // Load dashboard data
        this.loadDashboardStats();
        this.loadRecommendations();
        this.loadRecentTracks();
        
        // Add event listeners
        const refreshBtn = document.getElementById('refresh-recommendations');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadRecommendations();
                refreshBtn.querySelector('i').classList.add('fa-spin');
                setTimeout(() => {
                    refreshBtn.querySelector('i').classList.remove('fa-spin');
                }, 1000);
            });
        }
        
        const quickSettings = document.getElementById('quick-settings');
        if (quickSettings) {
            quickSettings.addEventListener('click', () => {
                this.navigateToPage('settings');
            });
        }
    }
    
    static async loadDashboardStats() {
        try {
            // In a real app, fetch stats from API
            // For now, use mock data
            document.getElementById('tracks-listened').textContent = '1,247';
            document.getElementById('minutes-listened').textContent = '8,452';
            document.getElementById('daily-streak').textContent = '7';
            
            // Load actual balance
            this.loadCurrencyBalance();
        } catch (error) {
            console.error('Error loading dashboard stats:', error);
        }
    }
    
    static async loadRecommendations() {
        const recommendationsList = document.getElementById('recommendations-list');
        if (!recommendationsList) return;
        
        recommendationsList.innerHTML = `
            <div class="recommendations-loading">
                ${Array(3).fill().map(() => `
                    <div class="recommendation-skeleton">
                        <div class="skeleton skeleton-circle"></div>
                        <div class="skeleton skeleton-text" style="width: 80%"></div>
                        <div class="skeleton skeleton-text" style="width: 60%"></div>
                    </div>
                `).join('')}
            </div>
        `;
        
        try {
            const recommendations = await API.getRecommendations();
            
            if (recommendations.length === 0) {
                recommendationsList.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-music"></i>
                        <h4>Нет рекомендаций</h4>
                        <p>Прослушайте несколько треков, чтобы получить рекомендации</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            recommendations.forEach(rec => {
                html += `
                    <div class="recommendation-item" data-track-id="${rec.id}">
                        <div class="recommendation-cover">
                            <img src="${rec.cover_uri || '/static/assets/images/default-cover.png'}" 
                                 alt="${rec.title}">
                            <button class="play-overlay" data-service="${rec.id.split('_')[0]}" 
                                    data-track-id="${rec.id.split('_')[1]}">
                                <i class="fas fa-play"></i>
                            </button>
                        </div>
                        <div class="recommendation-info">
                            <h4 class="recommendation-title">${rec.title}</h4>
                            <p class="recommendation-artist">${rec.artists.join(', ')}</p>
                            <span class="recommendation-badge ${rec.source}">${this.getRecommendationSource(rec.source)}</span>
                        </div>
                    </div>
                `;
            });
            
            recommendationsList.innerHTML = html;
            
            // Add play button handlers
            recommendationsList.querySelectorAll('.play-overlay').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const service = btn.dataset.service;
                    const trackId = btn.dataset.trackId;
                    
                    if (typeof Player !== 'undefined') {
                        Player.playTrack(service, trackId);
                    }
                });
            });
            
        } catch (error) {
            console.error('Error loading recommendations:', error);
            recommendationsList.innerHTML = `
                <div class="error-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Не удалось загрузить рекомендации</p>
                </div>
            `;
        }
    }
    
    static getRecommendationSource(source) {
        const sources = {
            'history_genre': 'По жанру',
            'history_artist': 'По исполнителю',
            'liked_similar': 'Похожие',
            'chart': 'В тренде',
            'new_releases': 'Новинки',
            'vk_recommendations': 'VK'
        };
        return sources[source] || 'Рекомендация';
    }
    
    static async loadRecentTracks() {
        const recentTracks = document.getElementById('recent-tracks');
        if (!recentTracks) return;
        
        try {
            const history = await API.getHistory(1);
            
            if (!history.history || history.history.length === 0) {
                recentTracks.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-history"></i>
                        <h4>История пуста</h4>
                        <p>Начните слушать музыку, чтобы заполнить историю</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            history.history.slice(0, 5).forEach(item => {
                const track = item.track_data;
                html += `
                    <div class="track-item" data-track-id="${item.track_id}">
                        <div class="track-item-cover">
                            <img src="${track.cover_uri || '/static/assets/images/default-cover.png'}" 
                                 alt="${track.title}">
                        </div>
                        <div class="track-item-info">
                            <div class="track-item-title">${track.title}</div>
                            <div class="track-item-artist">${track.artists.join(', ')}</div>
                            <div class="track-item-time">${Utils.formatDate(item.played_at)}</div>
                        </div>
                        <button class="track-item-play" data-service="${item.track_id.split('_')[0]}" 
                                data-track-id="${item.track_id.split('_')[1]}">
                            <i class="fas fa-play"></i>
                        </button>
                    </div>
                `;
            });
            
            recentTracks.innerHTML = html;
            
            // Add play button handlers
            recentTracks.querySelectorAll('.track-item-play').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const service = btn.dataset.service;
                    const trackId = btn.dataset.trackId;
                    
                    if (typeof Player !== 'undefined') {
                        Player.playTrack(service, trackId);
                    }
                });
            });
            
        } catch (error) {
            console.error('Error loading recent tracks:', error);
            recentTracks.innerHTML = `
                <div class="error-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Не удалось загрузить историю</p>
                </div>
            `;
        }
    }
    
    static initProfilePage() {
        // Load profile data
        this.loadProfileStats();
        this.checkConnectedServices();
        
        // Initialize form
        this.initProfileForm();
        this.initAvatarUpload();
        this.initServiceConnections();
    }
    
    static async loadProfileStats() {
        // In a real app, fetch from API
        document.getElementById('profile-tracks').textContent = '1,247';
        document.getElementById('profile-minutes').textContent = '8,452';
        document.getElementById('profile-friends').textContent = '24';
        document.getElementById('profile-items').textContent = '15';
    }
    
    static async checkConnectedServices() {
        try {
            const [yandexStatus, vkStatus] = await Promise.all([
                API.checkYandexToken(),
                API.checkVkToken()
            ]);
            
            const yandexService = document.getElementById('yandex-service');
            const vkService = document.getElementById('vk-service');
            const yandexStatusText = document.getElementById('yandex-status');
            const vkStatusText = document.getElementById('vk-status');
            
            if (yandexStatus.valid) {
                yandexStatusText.textContent = `Подключено как ${yandexStatus.account.login}`;
                yandexStatusText.style.color = 'var(--success)';
                yandexService.querySelector('button').textContent = 'Отключить';
            }
            
            if (vkStatus.valid) {
                vkStatusText.textContent = `Подключено как ${vkStatus.account.name}`;
                vkStatusText.style.color = 'var(--success)';
                vkService.querySelector('button').textContent = 'Отключить';
            }
            
        } catch (error) {
            console.error('Error checking services:', error);
        }
    }
    
    static initProfileForm() {
        const profileForm = document.getElementById('profile-form');
        if (!profileForm) return;
        
        profileForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const saveBtn = document.getElementById('save-profile-btn');
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Сохранение...';
            
            try {
                const data = {
                    display_name: document.getElementById('profile-display-name').value,
                    bio: document.getElementById('profile-bio').value
                };
                
                const result = await API.updateProfile(data);
                
                if (result.success) {
                    Utils.toast('Профиль успешно обновлен', 'success');
                    
                    // Update UI
                    this.updateUserUI(result);
                }
            } catch (error) {
                Utils.toast('Ошибка сохранения профиля', 'error');
            } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Сохранить изменения';
            }
        });
    }
    
    static initAvatarUpload() {
        const uploadBtn = document.getElementById('upload-avatar-btn');
        const avatarInput = document.getElementById('avatar-input');
        const removeBtn = document.getElementById('remove-avatar-btn');
        
        if (!uploadBtn || !avatarInput || !removeBtn) return;
        
        uploadBtn.addEventListener('click', () => {
            avatarInput.click();
        });
        
        avatarInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            // Validate file
            if (!file.type.startsWith('image/')) {
                Utils.toast('Пожалуйста, выберите изображение', 'error');
                return;
            }
            
            if (file.size > 5 * 1024 * 1024) {
                Utils.toast('Изображение должно быть меньше 5MB', 'error');
                return;
            }
            
            // Preview image
            const reader = new FileReader();
            reader.onload = async (e) => {
                const preview = document.getElementById('avatar-preview');
                if (preview) {
                    preview.querySelector('img').src = e.target.result;
                }
                
                // Upload to server
                try {
                    const saveBtn = document.getElementById('save-profile-btn');
                    saveBtn.disabled = true;
                    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
                    
                    const result = await API.updateProfile({
                        avatar: e.target.result
                    });
                    
                    if (result.success) {
                        Utils.toast('Аватар успешно обновлен', 'success');
                        this.updateUserUI(result);
                    }
                } catch (error) {
                    Utils.toast('Ошибка загрузки аватара', 'error');
                } finally {
                    const saveBtn = document.getElementById('save-profile-btn');
                    if (saveBtn) {
                        saveBtn.disabled = false;
                        saveBtn.innerHTML = '<i class="fas fa-save"></i> Сохранить изменения';
                    }
                }
            };
            reader.readAsDataURL(file);
        });
        
        removeBtn.addEventListener('click', async () => {
            try {
                const result = await API.updateProfile({
                    avatar: ''
                });
                
                if (result.success) {
                    Utils.toast('Аватар удален', 'success');
                    
                    // Clear preview
                    const preview = document.getElementById('avatar-preview');
                    if (preview) {
                        preview.querySelector('img').src = '/static/assets/images/default-avatar.png';
                    }
                    
                    this.updateUserUI(result);
                }
            } catch (error) {
                Utils.toast('Ошибка удаления аватара', 'error');
            }
        });
    }
    
    static initServiceConnections() {
        const connectYandexBtn = document.getElementById('connect-yandex-btn');
        const connectVkBtn = document.getElementById('connect-vk-btn');
        
        if (connectYandexBtn) {
            connectYandexBtn.addEventListener('click', () => {
                this.showServiceModal('yandex');
            });
        }
        
        if (connectVkBtn) {
            connectVkBtn.addEventListener('click', () => {
                this.showServiceModal('vk');
            });
        }
    }
    
    static showServiceModal(service) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.id = 'service-modal';
        modal.innerHTML = `
            <div class="modal-header">
                <h3>Подключить ${service === 'yandex' ? 'Яндекс.Музыку' : 'VK Музыку'}</h3>
                <button class="modal-close">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Токен доступа</label>
                    <input type="text" class="form-control" id="service-token" 
                           placeholder="Введите токен...">
                    <p class="form-text">
                        ${service === 'yandex' 
                            ? 'Чтобы получить токен, перейдите на <a href="https://oauth.yandex.ru" target="_blank">oauth.yandex.ru</a>' 
                            : 'Чтобы получить токен, перейдите на <a href="https://vk.com/dev/access_token" target="_blank">vk.com/dev/access_token</a>'}
                    </p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" id="cancel-service">Отмена</button>
                    <button class="btn btn-primary" id="save-service">Подключить</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const modalOverlay = document.getElementById('modal-overlay');
        modalOverlay.classList.add('active');
        modal.classList.add('active');
        
        // Add event listeners
        modal.querySelector('.modal-close').addEventListener('click', () => {
            this.closeModal();
            modal.remove();
        });
        
        modal.querySelector('#cancel-service').addEventListener('click', () => {
            this.closeModal();
            modal.remove();
        });
        
        modal.querySelector('#save-service').addEventListener('click', async () => {
            const token = modal.querySelector('#service-token').value.trim();
            
            if (!token) {
                Utils.toast('Введите токен', 'error');
                return;
            }
            
            const saveBtn = modal.querySelector('#save-service');
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Подключение...';
            
            try {
                const result = await API.saveToken(token, service);
                
                if (result.success) {
                    Utils.toast('Сервис успешно подключен', 'success');
                    this.closeModal();
                    modal.remove();
                    this.checkConnectedServices();
                }
            } catch (error) {
                Utils.toast('Ошибка подключения сервиса', 'error');
            } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = 'Подключить';
            }
        });
    }
    
    static initServiceWorker() {
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/service-worker.js')
                    .then(registration => {
                        console.log('ServiceWorker registration successful');
                    })
                    .catch(error => {
                        console.log('ServiceWorker registration failed:', error);
                    });
            });
        }
    }
    
    static initNetworkStatus() {
        // Update UI when network status changes
        const updateNetworkStatus = () => {
            if (!navigator.onLine) {
                Utils.toast('Отсутствует подключение к интернету', 'warning');
            } else {
                Utils.toast('Подключение восстановлено', 'success');
            }
        };
        
        window.addEventListener('online', updateNetworkStatus);
        window.addEventListener('offline', updateNetworkStatus);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', App.init);

// Make App available globally
window.App = App;