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

        // 新機能: 表示モードとプロジェクトフィルター
        const viewMode = ref('card');           // 'card' または 'list'
        const projectFilter = ref('all');       // 'all', 'completed', 'incomplete', 'custom'
        const customRangeMin = ref(0);          // カスタム範囲の最小値
        const customRangeMax = ref(100);        // カスタム範囲の最大値

        // 納品先・音声変換フィルター
        const destinationFilter = ref('all');   // 'all' または destination_id
        const ttsEngineFilter = ref('all');     // 'all' または tts_engine_id

        // マスターデータ
        const destinations = ref([]);
        const ttsEngines = ref([]);
        const publicationStatuses = ref([]);

        // 設定画面の状態
        const settingsTab = ref('destinations'); // 'destinations', 'tts-engines', 'publication-statuses'
        const editingItem = ref(null);           // 編集中のアイテム
        const newItemName = ref('');             // 新規追加時の名前

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

        // 完了プロジェクト（100%以上）
        const completedProjects = computed(() => {
            const list = projects.value || [];
            return list.filter(p => (p.progress || 0) >= 100);
        });

        // 未完了プロジェクト（100%未満）
        const incompleteProjects = computed(() => {
            const list = projects.value || [];
            return list.filter(p => (p.progress || 0) < 100);
        });

        // カスタム範囲フィルター
        const customFilteredProjects = computed(() => {
            const list = projects.value || [];
            const min = Number(customRangeMin.value) || 0;
            const max = Number(customRangeMax.value) || 100;
            return list.filter(p => {
                const progress = p.progress || 0;
                return progress >= min && progress <= max;
            });
        });

        // フィルター適用後のプロジェクト
        const filteredProjects = computed(() => {
            let list = projects.value || [];

            // 進捗フィルター
            switch (projectFilter.value) {
                case 'completed':
                    list = list.filter(p => (p.progress || 0) >= 100);
                    break;
                case 'incomplete':
                    list = list.filter(p => (p.progress || 0) < 100);
                    break;
                case 'custom':
                    const min = Number(customRangeMin.value) || 0;
                    const max = Number(customRangeMax.value) || 100;
                    list = list.filter(p => {
                        const progress = p.progress || 0;
                        return progress >= min && progress <= max;
                    });
                    break;
            }

            // 納品先フィルター
            if (destinationFilter.value !== 'all') {
                const destId = Number(destinationFilter.value);
                list = list.filter(p => p.destination_id === destId);
            }

            // 音声変換フィルター
            if (ttsEngineFilter.value !== 'all') {
                const ttsId = Number(ttsEngineFilter.value);
                list = list.filter(p => p.tts_engine_id === ttsId);
            }

            return list;
        });

        // フィルター + ソート適用後のプロジェクト
        const sortedFilteredProjects = computed(() => {
            const filtered = filteredProjects.value || [];
            const sorted = [...filtered];

            switch (sortBy.value) {
                case 'progress':
                    sorted.sort((a, b) => (b.progress || 0) - (a.progress || 0));
                    break;
                case 'progress_asc':
                    sorted.sort((a, b) => (a.progress || 0) - (b.progress || 0));
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

        // サブフォルダでグループ化されたトピック一覧
        const groupedTopics = computed(() => {
            const grouped = {};
            const topicList = filteredTopics.value || [];

            for (const topic of topicList) {
                const folder = topic.subfolder || '';
                if (!grouped[folder]) {
                    grouped[folder] = {
                        name: folder || 'ルート',
                        topics: [],
                        completed: 0,
                        in_progress: 0,
                        not_started: 0
                    };
                }
                grouped[folder].topics.push(topic);

                // ステータスカウント
                if (topic.status === 'completed') {
                    grouped[folder].completed++;
                } else if (topic.status === 'in_progress') {
                    grouped[folder].in_progress++;
                } else {
                    grouped[folder].not_started++;
                }
            }

            // サブフォルダ名でソートして配列に変換
            return Object.entries(grouped)
                .sort(([a], [b]) => {
                    // ルートは常に最初
                    if (a === '') return -1;
                    if (b === '') return 1;
                    return a.localeCompare(b, 'ja');
                })
                .map(([key, value]) => ({
                    key,
                    ...value,
                    progress: value.topics.length > 0
                        ? Math.round((value.completed / value.topics.length) * 100)
                        : 0
                }));
        });

        // サブフォルダの展開状態
        const expandedFolders = ref({});

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

        // マスターデータを取得
        async function fetchMasterData() {
            try {
                const [destData, ttsData, pubData] = await Promise.all([
                    API.getDestinations(),
                    API.getTtsEngines(),
                    API.getPublicationStatuses()
                ]);
                destinations.value = destData.destinations || [];
                ttsEngines.value = ttsData.tts_engines || [];
                publicationStatuses.value = pubData.publication_statuses || [];
            } catch (error) {
                console.error('Failed to fetch master data:', error);
            }
        }

        // プロジェクト設定を更新
        async function updateProjectSettings(projectId, settings) {
            try {
                const result = await API.updateProjectSettings(projectId, settings);
                // ローカル状態を更新
                const index = projects.value.findIndex(p => p.id === projectId);
                if (index !== -1 && result.project) {
                    projects.value[index] = { ...projects.value[index], ...result.project };
                }
                showToast('設定を更新しました', 'success');
            } catch (error) {
                console.error('Failed to update project settings:', error);
                showToast('設定の更新に失敗しました', 'error');
            }
        }

        // 納品先の変更
        function onDestinationChange(projectId, destinationId) {
            const destId = destinationId === '' ? null : Number(destinationId);
            const project = projects.value.find(p => p.id === projectId);
            if (project) {
                updateProjectSettings(projectId, {
                    destination_id: destId,
                    tts_engine_id: project.tts_engine_id
                });
            }
        }

        // 音声変換エンジンの変更
        function onTtsEngineChange(projectId, ttsEngineId) {
            const ttsId = ttsEngineId === '' ? null : Number(ttsEngineId);
            const project = projects.value.find(p => p.id === projectId);
            if (project) {
                updateProjectSettings(projectId, {
                    destination_id: project.destination_id,
                    tts_engine_id: ttsId
                });
            }
        }

        // 公開状態の変更
        function onPublicationStatusChange(projectId, statusId) {
            const pubStatusId = statusId === '' ? null : Number(statusId);
            const project = projects.value.find(p => p.id === projectId);
            if (project) {
                updateProjectSettings(projectId, {
                    destination_id: project.destination_id,
                    tts_engine_id: project.tts_engine_id,
                    publication_status_id: pubStatusId
                });
            }
        }

        // 公開状態のラベル取得（マスターデータから）
        function getPublicationStatusLabel(statusId) {
            if (!statusId) return '📋 公開状態';
            const status = publicationStatuses.value.find(s => s.id === statusId);
            return status ? status.name : '📋 公開状態';
        }

        // 公開状態のバッジクラス取得
        function getPublicationStatusClass(statusId) {
            if (!statusId) return 'bg-gray-100 text-gray-700';
            const status = publicationStatuses.value.find(s => s.id === statusId);
            if (!status) return 'bg-gray-100 text-gray-700';
            // 名前に基づいてクラスを決定
            if (status.name.includes('無料')) return 'bg-green-100 text-green-700';
            if (status.name.includes('有料')) return 'bg-yellow-100 text-yellow-700';
            return 'bg-gray-100 text-gray-700';
        }

        // ========== マスター管理メソッド ==========

        // 納品先の追加
        async function addDestination() {
            if (!newItemName.value.trim()) return;
            try {
                await API.createDestination({ name: newItemName.value.trim() });
                newItemName.value = '';
                await fetchMasterData();
                showToast('納品先を追加しました', 'success');
            } catch (error) {
                console.error('Failed to add destination:', error);
                showToast('追加に失敗しました', 'error');
            }
        }

        // 納品先の更新
        async function updateDestination(id, name) {
            try {
                await API.updateDestination(id, { name });
                editingItem.value = null;
                await fetchMasterData();
                showToast('更新しました', 'success');
            } catch (error) {
                console.error('Failed to update destination:', error);
                showToast('更新に失敗しました', 'error');
            }
        }

        // 納品先の削除
        async function deleteDestination(id) {
            if (!confirm('この納品先を削除しますか？関連するプロジェクトの納品先は未設定になります。')) return;
            try {
                await API.deleteDestination(id);
                await fetchMasterData();
                await fetchProjects(); // プロジェクトも再取得
                showToast('削除しました', 'success');
            } catch (error) {
                console.error('Failed to delete destination:', error);
                showToast('削除に失敗しました', 'error');
            }
        }

        // 音声変換エンジンの追加
        async function addTtsEngine() {
            if (!newItemName.value.trim()) return;
            try {
                await API.createTtsEngine({ name: newItemName.value.trim() });
                newItemName.value = '';
                await fetchMasterData();
                showToast('音声変換エンジンを追加しました', 'success');
            } catch (error) {
                console.error('Failed to add TTS engine:', error);
                showToast('追加に失敗しました', 'error');
            }
        }

        // 音声変換エンジンの更新
        async function updateTtsEngine(id, name) {
            try {
                await API.updateTtsEngine(id, { name });
                editingItem.value = null;
                await fetchMasterData();
                showToast('更新しました', 'success');
            } catch (error) {
                console.error('Failed to update TTS engine:', error);
                showToast('更新に失敗しました', 'error');
            }
        }

        // 音声変換エンジンの削除
        async function deleteTtsEngine(id) {
            if (!confirm('この音声変換エンジンを削除しますか？関連するプロジェクトの設定は未設定になります。')) return;
            try {
                await API.deleteTtsEngine(id);
                await fetchMasterData();
                await fetchProjects(); // プロジェクトも再取得
                showToast('削除しました', 'success');
            } catch (error) {
                console.error('Failed to delete TTS engine:', error);
                showToast('削除に失敗しました', 'error');
            }
        }

        // 公開状態の追加
        async function addPublicationStatus() {
            if (!newItemName.value.trim()) return;
            try {
                await API.createPublicationStatus({ name: newItemName.value.trim() });
                newItemName.value = '';
                await fetchMasterData();
                showToast('追加しました', 'success');
            } catch (error) {
                console.error('Failed to create publication status:', error);
                showToast('追加に失敗しました', 'error');
            }
        }

        // 公開状態の更新
        async function updatePublicationStatus(id, name) {
            try {
                await API.updatePublicationStatus(id, { name });
                editingItem.value = null;
                await fetchMasterData();
                showToast('更新しました', 'success');
            } catch (error) {
                console.error('Failed to update publication status:', error);
                showToast('更新に失敗しました', 'error');
            }
        }

        // 公開状態の削除
        async function deletePublicationStatus(id) {
            if (!confirm('この公開状態を削除しますか？関連するプロジェクトの設定は未設定になります。')) return;
            try {
                await API.deletePublicationStatus(id);
                await fetchMasterData();
                await fetchProjects(); // プロジェクトも再取得
                showToast('削除しました', 'success');
            } catch (error) {
                console.error('Failed to delete publication status:', error);
                showToast('削除に失敗しました', 'error');
            }
        }

        // 編集開始
        function startEditing(item) {
            editingItem.value = { ...item };
        }

        // 編集キャンセル
        function cancelEditing() {
            editingItem.value = null;
        }

        // 編集保存
        function saveEditing() {
            if (!editingItem.value || !editingItem.value.name.trim()) return;
            if (settingsTab.value === 'destinations') {
                updateDestination(editingItem.value.id, editingItem.value.name.trim());
            } else if (settingsTab.value === 'tts-engines') {
                updateTtsEngine(editingItem.value.id, editingItem.value.name.trim());
            } else if (settingsTab.value === 'publication-statuses') {
                updatePublicationStatus(editingItem.value.id, editingItem.value.name.trim());
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

        // サブフォルダの展開/折りたたみ
        function toggleFolder(folderKey) {
            expandedFolders.value[folderKey] = !expandedFolders.value[folderKey];
        }

        // フォルダが展開されているか
        function isFolderExpanded(folderKey) {
            // デフォルトは展開状態
            return expandedFolders.value[folderKey] !== false;
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
            await Promise.all([
                fetchProjects(),
                fetchMasterData()
            ]);
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

            // 新機能: 表示モードとフィルター
            viewMode,
            projectFilter,
            customRangeMin,
            customRangeMax,

            // 納品先・音声変換フィルター
            destinationFilter,
            ttsEngineFilter,

            // マスターデータ
            destinations,
            ttsEngines,
            publicationStatuses,

            // 設定画面
            settingsTab,
            editingItem,
            newItemName,

            // 算出プロパティ
            sortedProjects,
            filteredTopics,
            groupedTopics,
            expandedFolders,
            completedProjects,
            incompleteProjects,
            customFilteredProjects,
            filteredProjects,
            sortedFilteredProjects,

            // メソッド
            selectProject,
            triggerScan,
            openFolder,
            formatDateTime,
            formatTime,
            getFilterCount,
            toggleFolder,
            isFolderExpanded,

            // プロジェクト設定
            onDestinationChange,
            onTtsEngineChange,
            onPublicationStatusChange,
            getPublicationStatusLabel,
            getPublicationStatusClass,

            // マスター管理
            addDestination,
            updateDestination,
            deleteDestination,
            addTtsEngine,
            updateTtsEngine,
            deleteTtsEngine,
            addPublicationStatus,
            updatePublicationStatus,
            deletePublicationStatus,
            startEditing,
            cancelEditing,
            saveEditing
        };
    }
});

// アプリマウント
app.mount('#app');
