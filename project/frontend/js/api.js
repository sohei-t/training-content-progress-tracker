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
     * PUTリクエスト
     */
    async put(endpoint, body = {}, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;

        try {
            const response = await fetch(url, {
                method: 'PUT',
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
            console.error(`API PUT error: ${url}`, error);
            throw error;
        }
    },

    /**
     * DELETEリクエスト
     */
    async delete(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;

        try {
            const response = await fetch(url, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API DELETE error: ${url}`, error);
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

    // ========== プロジェクト設定API ==========

    /**
     * プロジェクト設定更新
     */
    async updateProjectSettings(projectId, settings) {
        this.clearCache('/projects');
        return await this.put(`/projects/${projectId}/settings`, settings);
    },

    // ========== 納品先マスターAPI ==========

    /**
     * 納品先一覧取得
     */
    async getDestinations() {
        return await this.get('/destinations');
    },

    /**
     * 納品先作成
     */
    async createDestination(data) {
        this.clearCache('/destinations');
        return await this.post('/destinations', data);
    },

    /**
     * 納品先更新
     */
    async updateDestination(id, data) {
        this.clearCache('/destinations');
        return await this.put(`/destinations/${id}`, data);
    },

    /**
     * 納品先削除
     */
    async deleteDestination(id) {
        this.clearCache('/destinations');
        return await this.delete(`/destinations/${id}`);
    },

    /**
     * 納品先並べ替え
     */
    async reorderDestinations(data) {
        this.clearCache('/destinations');
        return await this.put('/destinations/reorder', data);
    },

    // ========== 音声変換エンジンマスターAPI ==========

    /**
     * 音声変換エンジン一覧取得
     */
    async getTtsEngines() {
        return await this.get('/tts-engines');
    },

    /**
     * 音声変換エンジン作成
     */
    async createTtsEngine(data) {
        this.clearCache('/tts-engines');
        return await this.post('/tts-engines', data);
    },

    /**
     * 音声変換エンジン更新
     */
    async updateTtsEngine(id, data) {
        this.clearCache('/tts-engines');
        return await this.put(`/tts-engines/${id}`, data);
    },

    /**
     * 音声変換エンジン削除
     */
    async deleteTtsEngine(id) {
        this.clearCache('/tts-engines');
        return await this.delete(`/tts-engines/${id}`);
    },

    /**
     * 音声変換エンジン並べ替え
     */
    async reorderTtsEngines(data) {
        this.clearCache('/tts-engines');
        return await this.put('/tts-engines/reorder', data);
    },

    // ========== 公開状態マスターAPI ==========

    /**
     * 公開状態一覧取得
     */
    async getPublicationStatuses() {
        return await this.get('/publication-statuses');
    },

    /**
     * 公開状態作成
     */
    async createPublicationStatus(data) {
        this.clearCache('/publication-statuses');
        return await this.post('/publication-statuses', data);
    },

    /**
     * 公開状態更新
     */
    async updatePublicationStatus(id, data) {
        this.clearCache('/publication-statuses');
        return await this.put(`/publication-statuses/${id}`, data);
    },

    /**
     * 公開状態削除
     */
    async deletePublicationStatus(id) {
        this.clearCache('/publication-statuses');
        return await this.delete(`/publication-statuses/${id}`);
    },

    /**
     * 公開状態並べ替え
     */
    async reorderPublicationStatuses(data) {
        this.clearCache('/publication-statuses');
        return await this.put('/publication-statuses/reorder', data);
    },

    // ========== チェック進捗マスターAPI ==========

    /**
     * チェック進捗一覧取得
     */
    async getCheckStatuses() {
        return await this.get('/check-statuses');
    },

    /**
     * チェック進捗作成
     */
    async createCheckStatus(data) {
        this.clearCache('/check-statuses');
        return await this.post('/check-statuses', data);
    },

    /**
     * チェック進捗更新
     */
    async updateCheckStatus(id, data) {
        this.clearCache('/check-statuses');
        return await this.put(`/check-statuses/${id}`, data);
    },

    /**
     * チェック進捗削除
     */
    async deleteCheckStatus(id) {
        this.clearCache('/check-statuses');
        return await this.delete(`/check-statuses/${id}`);
    },

    /**
     * チェック進捗並べ替え
     */
    async reorderCheckStatuses(data) {
        this.clearCache('/check-statuses');
        return await this.put('/check-statuses/reorder', data);
    },

    // ========== RAG API ==========

    /**
     * RAGインデックス状態取得
     */
    async getRagStatus(projectId) {
        return await this.get(`/projects/${projectId}/rag-status`, { noCache: true });
    },

    /**
     * RAGインデックス構築開始
     */
    async buildRagIndex(projectId) {
        this.clearCache();
        return await this.post(`/projects/${projectId}/rag-build`);
    },

    /**
     * RAGインデックス削除
     */
    async deleteRagIndex(projectId) {
        this.clearCache();
        return await this.delete(`/projects/${projectId}/rag-index`);
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
