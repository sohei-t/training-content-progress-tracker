/**
 * API通信サービス
 * パフォーマンス最適化: リクエストキャッシュ、デバウンス、エラーリトライ
 */

const API = {
    baseUrl: '/api',
    cache: new Map(),
    cacheTimeout: 5000, // 5秒キャッシュ

    /**
     * キャッシュ付きGETリクエスト
     */
    async get(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const cacheKey = url;

        // キャッシュチェック
        if (!options.noCache) {
            const cached = this.cache.get(cacheKey);
            if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }

        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // キャッシュに保存
            this.cache.set(cacheKey, {
                data,
                timestamp: Date.now()
            });

            return data;
        } catch (error) {
            console.error(`API GET error: ${url}`, error);
            throw error;
        }
    },

    /**
     * POSTリクエスト
     */
    async post(endpoint, body = {}, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API POST error: ${url}`, error);
            throw error;
        }
    },

    /**
     * キャッシュをクリア
     */
    clearCache(endpoint = null) {
        if (endpoint) {
            const url = `${this.baseUrl}${endpoint}`;
            this.cache.delete(url);
        } else {
            this.cache.clear();
        }
    },

    // ========== プロジェクトAPI ==========

    /**
     * プロジェクト一覧取得
     */
    async getProjects() {
        const data = await this.get('/projects');
        return data.projects || [];
    },

    /**
     * プロジェクト詳細取得
     */
    async getProject(projectId) {
        return await this.get(`/projects/${projectId}`);
    },

    /**
     * プロジェクトのトピック一覧取得
     */
    async getProjectTopics(projectId) {
        return await this.get(`/projects/${projectId}/topics`);
    },

    // ========== スキャンAPI ==========

    /**
     * スキャン実行
     */
    async triggerScan(projectId = null, scanType = 'full') {
        this.clearCache(); // スキャン時はキャッシュクリア
        return await this.post('/scan', {
            project_id: projectId,
            scan_type: scanType
        });
    },

    // ========== 統計API ==========

    /**
     * 全体統計取得
     */
    async getStats() {
        return await this.get('/stats');
    },

    // ========== ヘルスチェック ==========

    /**
     * ヘルスチェック
     */
    async healthCheck() {
        return await this.get('/health', { noCache: true });
    }
};

// デバウンス関数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// スロットル関数
function throttle(func, limit) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// エクスポート（グローバル）
window.API = API;
window.debounce = debounce;
window.throttle = throttle;
