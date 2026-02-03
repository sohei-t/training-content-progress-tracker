/**
 * Vue.jsメインアプリケーション
 * パフォーマンス最適化: 仮想スクロール対応、リアクティブ最適化
 */

const { createApp, ref, computed, onMounted, onUnmounted, watch, nextTick } = Vue;

const app = createApp({
    setup() {
        // ========== 状態 ==========
        const projects = ref([]);
        const selectedProject = ref(null);
        const topics = ref([]);
        const topicSummary = ref({ completed: 0, in_progress: 0, not_started: 0 });
        const stats = ref({
            totalProjects: 0,
            totalTopics: 0,
            completedTopics: 0,
            overallProgress: 0,
            htmlTotal: 0,
            txtTotal: 0,
            mp3Total: 0
        });

        const currentView = ref('dashboard');
        const isLoading = ref(true);
        const isScanning = ref(false);
        const wsConnected = ref(false);
        const lastUpdated = ref(null);
        const sortBy = ref('name');
        const topicFilter = ref('all');
        const toasts = ref([]);

        // フィルターラベル
        const filterLabels = {
            all: '全て',
            completed: '完了',
            in_progress: '進行中',
            not_started: '未着手'
        };

        // ========== 算出プロパティ ==========

        // ソートされたプロジェクト一覧
        const sortedProjects = computed(() => {
            const sorted = [...projects.value];

            switch (sortBy.value) {
                case 'progress':
                    sorted.sort((a, b) => (b.progress || 0) - (a.progress || 0));
                    break;
                case 'updated':
                    sorted.sort((a, b) => {
                        const dateA = a.last_scanned_at ? new Date(a.last_scanned_at) : new Date(0);
                        const dateB = b.last_scanned_at ? new Date(b.last_scanned_at) : new Date(0);
                        return dateB - dateA;
                    });
                    break;
                case 'name':
                default:
                    sorted.sort((a, b) => a.name.localeCompare(b.name, 'ja'));
            }

            return sorted;
        });

        // フィルタリングされたトピック一覧
        const filteredTopics = computed(() => {
            if (topicFilter.value === 'all') {
                return topics.value;
            }
            return topics.value.filter(t => t.status === topicFilter.value);
        });

        // ========== メソッド ==========

        // プロジェクト一覧を取得
        async function fetchProjects() {
            try {
                const data = await API.getProjects();
                projects.value = data;
                lastUpdated.value = new Date().toISOString();
                updateStats();
            } catch (error) {
                console.error('Failed to fetch projects:', error);
                showToast('プロジェクトの取得に失敗しました', 'error');
            }
        }

        // 統計を更新
        function updateStats() {
            const p = projects.value;
            stats.value = {
                totalProjects: p.length,
                totalTopics: p.reduce((sum, proj) => sum + (proj.total_topics || 0), 0),
                completedTopics: p.reduce((sum, proj) => sum + (proj.completed_topics || 0), 0),
                overallProgress: calculateOverallProgress(p),
                htmlTotal: p.reduce((sum, proj) => sum + (proj.html_count || 0), 0),
                txtTotal: p.reduce((sum, proj) => sum + (proj.txt_count || 0), 0),
                mp3Total: p.reduce((sum, proj) => sum + (proj.mp3_count || 0), 0)
            };
        }

        // 全体進捗率を計算
        function calculateOverallProgress(projectList) {
            const total = projectList.reduce((sum, p) => sum + (p.total_topics || 0), 0);
            if (total === 0) return 0;

            const html = projectList.reduce((sum, p) => sum + (p.html_count || 0), 0);
            const txt = projectList.reduce((sum, p) => sum + (p.txt_count || 0), 0);
            const mp3 = projectList.reduce((sum, p) => sum + (p.mp3_count || 0), 0);

            return ((html * 0.4) + (txt * 0.3) + (mp3 * 0.3)) / total * 100;
        }

        // プロジェクト選択
        async function selectProject(project) {
            selectedProject.value = project;
            currentView.value = 'detail';
            topicFilter.value = 'all';

            try {
                const data = await API.getProjectTopics(project.id);
                topics.value = data.topics || [];
                topicSummary.value = data.summary || { completed: 0, in_progress: 0, not_started: 0 };
            } catch (error) {
                console.error('Failed to fetch topics:', error);
                showToast('トピックの取得に失敗しました', 'error');
            }
        }

        // フィルターカウント取得
        function getFilterCount(filter) {
            if (filter === 'all') return topics.value.length;
            return topics.value.filter(t => t.status === filter).length;
        }

        // スキャン実行
        async function triggerScan() {
            if (isScanning.value) return;

            isScanning.value = true;
            showToast('スキャンを開始しました', 'info');

            try {
                await API.triggerScan();
                // スキャン完了はWebSocketで通知される
            } catch (error) {
                console.error('Failed to trigger scan:', error);
                showToast('スキャンの開始に失敗しました', 'error');
                isScanning.value = false;
            }
        }

        // フォルダを開く（デスクトップアプリ用）
        function openFolder(path) {
            // ブラウザからは直接開けないため、通知のみ
            showToast(`パス: ${path}`, 'info');
        }

        // トースト通知
        function showToast(message, type = 'info') {
            const id = Date.now();
            toasts.value.push({ id, message, type });

            setTimeout(() => {
                toasts.value = toasts.value.filter(t => t.id !== id);
            }, 3000);
        }

        // 日時フォーマット
        function formatDateTime(dateStr) {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleString('ja-JP', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        // 時刻フォーマット
        function formatTime(dateStr) {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleTimeString('ja-JP', {
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        // ========== WebSocket イベントハンドラー ==========

        function setupWebSocket() {
            // 接続状態
            wsService.on('connected', () => {
                wsConnected.value = true;
                showToast('リアルタイム接続確立', 'success');
            });

            wsService.on('disconnected', () => {
                wsConnected.value = false;
            });

            wsService.on('reconnecting', ({ attempt, delay }) => {
                showToast(`再接続中... (${attempt}回目)`, 'info');
            });

            // プロジェクト更新
            wsService.on('project_updated', (data) => {
                const project = data.project;
                const index = projects.value.findIndex(p => p.id === project.id);

                if (index !== -1) {
                    projects.value[index] = { ...projects.value[index], ...project };
                } else {
                    projects.value.push(project);
                }

                // 選択中のプロジェクトを更新
                if (selectedProject.value && selectedProject.value.id === project.id) {
                    selectedProject.value = { ...selectedProject.value, ...project };
                }

                updateStats();
                lastUpdated.value = new Date().toISOString();
            });

            // トピック変更
            wsService.on('topic_changed', (data) => {
                const { project_id, topic } = data;

                if (selectedProject.value && selectedProject.value.id === project_id) {
                    const index = topics.value.findIndex(t => t.id === topic.id);
                    if (index !== -1) {
                        topics.value[index] = { ...topics.value[index], ...topic };
                    }
                }
            });

            // スキャン開始
            wsService.on('scan_started', (data) => {
                isScanning.value = true;
                showToast('スキャン実行中...', 'info');
            });

            // スキャン完了
            wsService.on('scan_completed', (data) => {
                isScanning.value = false;
                fetchProjects(); // 最新データを取得
                showToast(
                    `スキャン完了: ${data.result?.projects_scanned || 0}プロジェクト`,
                    'success'
                );
            });

            // 接続開始
            wsService.connect();
        }

        // ========== ライフサイクル ==========

        onMounted(async () => {
            // 初期データ取得
            await fetchProjects();
            isLoading.value = false;

            // WebSocket接続
            setupWebSocket();
        });

        onUnmounted(() => {
            wsService.disconnect();
        });

        // ========== 戻り値 ==========

        return {
            // 状態
            projects,
            selectedProject,
            topics,
            topicSummary,
            stats,
            currentView,
            isLoading,
            isScanning,
            wsConnected,
            lastUpdated,
            sortBy,
            topicFilter,
            toasts,
            filterLabels,

            // 算出プロパティ
            sortedProjects,
            filteredTopics,

            // メソッド
            selectProject,
            triggerScan,
            openFolder,
            formatDateTime,
            formatTime,
            getFilterCount
        };
    }
});

// アプリマウント
app.mount('#app');
