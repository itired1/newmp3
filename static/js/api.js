// API Client

class ApiClient {
    constructor() {
        this.baseUrl = '/api';
        this.defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = { ...this.defaultHeaders, ...options.headers };
        
        const config = {
            ...options,
            headers,
            credentials: 'same-origin'
        };
        
        try {
            const response = await fetch(url, config);
            
            // Handle HTTP errors
            if (!response.ok) {
                const error = await this.handleError(response);
                throw error;
            }
            
            // Handle empty responses
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
            
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }
    
    async handleError(response) {
        let message = `HTTP ${response.status}`;
        let data = null;
        
        try {
            data = await response.json();
            message = data.error || data.message || message;
        } catch {
            try {
                message = await response.text() || message;
            } catch {
                // Use default message
            }
        }
        
        const error = new Error(message);
        error.status = response.status;
        error.data = data;
        
        // Show error toast
        if (message && typeof Utils !== 'undefined') {
            Utils.toast(message, 'error');
        }
        
        // Handle specific status codes
        switch (response.status) {
            case 401:
                // Unauthorized - redirect to login
                if (window.location.pathname !== '/login') {
                    window.location.href = '/login';
                }
                break;
            case 403:
                // Forbidden
                Utils.toast('Доступ запрещен', 'error');
                break;
            case 429:
                // Rate limit exceeded
                Utils.toast('Слишком много запросов. Попробуйте позже.', 'warning');
                break;
            case 500:
                // Server error
                Utils.toast('Внутренняя ошибка сервера', 'error');
                break;
        }
        
        return error;
    }
    
    // Authentication
    async login(username, password) {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        
        const response = await fetch('/login', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            return { success: true };
        } else {
            const text = await response.text();
            throw new Error(text || 'Ошибка входа');
        }
    }
    
    async register(userData) {
        const formData = new FormData();
        Object.keys(userData).forEach(key => {
            formData.append(key, userData[key]);
        });
        
        const response = await fetch('/register', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            return { success: true };
        } else {
            const text = await response.text();
            throw new Error(text || 'Ошибка регистрации');
        }
    }
    
    async verifyEmail(email, code) {
        return this.request('/verify', {
            method: 'POST',
            body: JSON.stringify({ email, code })
        });
    }
    
    async resendVerification(email) {
        return this.request('/resend_verification', {
            method: 'POST',
            body: JSON.stringify({ email })
        });
    }
    
    // User Profile
    async getProfile() {
        return this.request('/profile');
    }
    
    async updateProfile(data) {
        return this.request('/profile', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    // Currency
    async getCurrencyBalance() {
        return this.request('/currency/balance');
    }
    
    async getCurrencyHistory(page = 1) {
        return this.request(`/currency/history?page=${page}`);
    }
    
    // Shop
    async getShopCategories() {
        return this.request('/shop/categories');
    }
    
    async getShopItems(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/shop/items?${query}`);
    }
    
    async buyItem(itemId) {
        return this.request(`/shop/buy/${itemId}`, {
            method: 'POST'
        });
    }
    
    // Inventory
    async getInventory() {
        return this.request('/inventory');
    }
    
    async equipItem(itemId) {
        return this.request(`/inventory/equip/${itemId}`, {
            method: 'POST'
        });
    }
    
    async unequipItem(itemId) {
        return this.request(`/inventory/unequip/${itemId}`, {
            method: 'POST'
        });
    }
    
    // Music
    async checkYandexToken() {
        return this.request('/music/check_yandex');
    }
    
    async checkVkToken() {
        return this.request('/music/check_vk');
    }
    
    async saveToken(token, service) {
        return this.request('/music/save_token', {
            method: 'POST',
            body: JSON.stringify({ token, service })
        });
    }
    
    async getRecommendations() {
        return this.request('/recommendations');
    }
    
    async getPlaylists() {
        return this.request('/playlists');
    }
    
    async getPlaylist(service, playlistId) {
        return this.request(`/playlist/${service}_${playlistId}`);
    }
    
    async getLikedTracks() {
        return this.request('/liked');
    }
    
    async getTrackUrl(service, trackId) {
        return this.request(`/play/${service}_${trackId}`);
    }
    
    // History
    async getHistory(page = 1) {
        return this.request(`/history?page=${page}`);
    }
    
    // Daily Reward
    async claimDailyReward() {
        return this.request('/daily_reward', {
            method: 'POST'
        });
    }
    
    // Settings
    async getSettings() {
        return this.request('/settings');
    }
    
    async updateSettings(data) {
        return this.request('/settings', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }
    
    // Friends
    async getFriends() {
        return this.request('/friends');
    }
    
    async addFriend(friendId) {
        return this.request(`/friends/add/${friendId}`, {
            method: 'POST'
        });
    }
    
    // Themes
    async getThemes() {
        return this.request('/themes');
    }
    
    async createTheme(data) {
        return this.request('/themes', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    async deleteTheme(themeId) {
        return this.request(`/themes/${themeId}`, {
            method: 'DELETE'
        });
    }
    
    // Search
    async search(query) {
        return this.request(`/search?q=${encodeURIComponent(query)}`);
    }
    
    // Admin
    async getAdminStats() {
        return this.request('/admin/stats');
    }
    
    async getAdminUsers(page = 1) {
        return this.request(`/admin/users?page=${page}`);
    }
    
    async adminAddCurrency(userId, amount, reason = 'admin_grant') {
        return this.request('/admin/add_currency', {
            method: 'POST',
            body: JSON.stringify({ user_id: userId, amount, reason })
        });
    }
    
    // Health Check
    async checkHealth() {
        try {
            const response = await fetch('/health');
            return await response.json();
        } catch {
            return { status: 'unhealthy' };
        }
    }
}

// Create global API instance
const API = new ApiClient();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}