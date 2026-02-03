# システムアーキテクチャ設計 - 革新的アプローチ

## 1. アーキテクチャ概要

### 1.1 設計思想

```
┌─────────────────────────────────────────────────────────────────────┐
│                    イベント駆動アーキテクチャ                         │
│                                                                     │
│  ファイルシステム → イベント → 非同期処理 → WebSocket → リアルタイムUI  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 全体構成図

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              クライアント層                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Vue.js 3 (CDN)                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │   │
│  │  │  Dashboard   │  │ProjectDetail │  │ ProgressChart│           │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │   │
│  │         ↑               ↑                  ↑                    │   │
│  │         └───────────────┴──────────────────┘                    │   │
│  │                         │                                        │   │
│  │  ┌──────────────────────┴───────────────────────┐               │   │
│  │  │              State Management                 │               │   │
│  │  │  (reactive refs + provide/inject)            │               │   │
│  │  └──────────────────────┬───────────────────────┘               │   │
│  │                         │                                        │   │
│  │  ┌──────────────────────┴───────────────────────┐               │   │
│  │  │   API Service    │   WebSocket Service       │               │   │
│  │  └──────────────────────┬───────────────────────┘               │   │
│  └─────────────────────────┼───────────────────────────────────────┘   │
└────────────────────────────┼───────────────────────────────────────────┘
                             │
                             │ HTTP/WebSocket
                             ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                              サーバー層                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      FastAPI (uvicorn)                          │   │
│  │                                                                 │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                │   │
│  │  │ REST API   │  │ WebSocket  │  │ Static     │                │   │
│  │  │ /api/*     │  │ /ws        │  │ /          │                │   │
│  │  └─────┬──────┘  └─────┬──────┘  └────────────┘                │   │
│  │        │               │                                        │   │
│  │        └───────────────┼────────────────────────┐              │   │
│  │                        │                        │              │   │
│  │  ┌─────────────────────┴────────────────────┐   │              │   │
│  │  │            Connection Pool               │   │              │   │
│  │  │   (WebSocket接続管理 + broadcast)         │   │              │   │
│  │  └─────────────────────┬────────────────────┘   │              │   │
│  │                        │                        │              │   │
│  │  ┌─────────────────────┴───────────────────────┴┐              │   │
│  │  │              Service Layer                   │              │   │
│  │  │  ┌──────────────┐  ┌──────────────┐          │              │   │
│  │  │  │ ScanService  │  │ ProjectService│          │              │   │
│  │  │  └──────┬───────┘  └──────┬───────┘          │              │   │
│  │  └─────────┼─────────────────┼──────────────────┘              │   │
│  │            │                 │                                  │   │
│  │  ┌─────────┴─────────────────┴──────────────────┐              │   │
│  │  │              Core Components                 │              │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐    │              │   │
│  │  │  │ Scanner  │  │ Watcher  │  │WBSParser │    │              │   │
│  │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘    │              │   │
│  │  └───────┼─────────────┼─────────────┼──────────┘              │   │
│  └──────────┼─────────────┼─────────────┼──────────────────────────┘   │
└─────────────┼─────────────┼─────────────┼──────────────────────────────┘
              │             │             │
              ↓             ↓             ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                              データ層                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   SQLite + aiosqlite                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │   │
│  │  │   projects   │  │    topics    │  │ scan_history │           │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   File System (Learning-Curricula)               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │   │
│  │  │ API入門講座   │  │ GCP入門講座   │  │ Linux入門講座 │  ...     │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 技術スタック詳細

### 2.1 バックエンド

| カテゴリ | 技術 | バージョン | 選定理由 |
|---------|-----|---------|---------|
| フレームワーク | FastAPI | 0.115+ | 非同期ネイティブ、WebSocket対応、自動ドキュメント |
| サーバー | uvicorn | 0.30+ | ASGI対応、高パフォーマンス |
| データベース | SQLite | 3.40+ | 軽量、WALモード、単一ファイル |
| 非同期DB | aiosqlite | 0.20+ | asyncio完全対応 |
| ファイル監視 | watchdog | 4.0+ | クロスプラットフォーム、低リソース |
| 非同期IO | aiofiles | 24.1+ | 非同期ファイル読み書き |
| ハッシュ | xxhash | 3.4+ | MD5の10倍高速 |

### 2.2 フロントエンド

| カテゴリ | 技術 | 選定理由 |
|---------|-----|---------|
| フレームワーク | Vue.js 3 (CDN) | 軽量、Composition API、ビルド不要 |
| CSS | Tailwind CSS (CDN) | ユーティリティファースト、高速開発 |
| チャート | Chart.js (CDN) | 軽量、アニメーション対応 |
| WebSocket | Native API | 追加依存なし |

### 2.3 CDN URLs

```html
<!-- Vue.js 3 -->
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>

<!-- Tailwind CSS -->
<script src="https://cdn.tailwindcss.com"></script>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

---

## 3. コンポーネント設計

### 3.1 バックエンドコンポーネント

#### 3.1.1 WBSパーサー (`backend/wbs_parser.py`)

```python
from typing import Protocol, List, Optional
from dataclasses import dataclass

@dataclass
class Topic:
    id: str
    chapter: str
    title: str
    base_name: str

class WBSParser(Protocol):
    def parse(self, data: dict) -> List[Topic]: ...

class ObjectFormatParser:
    """オブジェクト型WBSパーサー（API入門講座形式）"""
    def parse(self, data: dict) -> List[Topic]:
        topics = []
        phases = data.get('phases', {})
        for phase_key, phase in phases.items():
            if 'chapters' in phase:
                for ch_key, chapter in phase['chapters'].items():
                    for topic in chapter.get('topics', []):
                        topics.append(Topic(
                            id=topic['id'],
                            chapter=chapter.get('name', ch_key),
                            title=topic['title'],
                            base_name=topic['base_name']
                        ))
        return topics

class ArrayFormatParser:
    """配列型WBSパーサー（生成AI入門講座形式）"""
    def parse(self, data: dict) -> List[Topic]:
        # ファイル名マッピングから直接取得
        # または content/ フォルダをスキャンして推論
        pass

def detect_and_parse(wbs_path: str) -> List[Topic]:
    """自動形式検出 + パース"""
    data = load_json(wbs_path)
    phases = data.get('phases', {})

    if isinstance(phases, dict):
        return ObjectFormatParser().parse(data)
    elif isinstance(phases, list):
        return ArrayFormatParser().parse(data)
    else:
        raise ValueError("Unknown WBS format")
```

#### 3.1.2 非同期スキャナー (`backend/scanner.py`)

```python
import asyncio
from pathlib import Path
import xxhash
import aiofiles

class AsyncScanner:
    def __init__(self, db: Database, content_path: Path):
        self.db = db
        self.content_path = content_path
        self.hash_cache: dict[str, str] = {}  # LRUキャッシュ

    async def scan_project(self, project_path: Path) -> ScanResult:
        """プロジェクト全体をスキャン"""
        content_dir = project_path / 'content'

        # 並列ファイルスキャン
        tasks = []
        async for file_path in self._list_files(content_dir):
            tasks.append(self._scan_file(file_path))

        results = await asyncio.gather(*tasks)
        return ScanResult(files=results)

    async def _scan_file(self, file_path: Path) -> FileInfo:
        """個別ファイルスキャン（ハッシュ計算）"""
        async with aiofiles.open(file_path, 'rb') as f:
            content = await f.read()
            hash_value = xxhash.xxh64(content).hexdigest()

        return FileInfo(
            path=file_path,
            hash=hash_value,
            changed=self._is_changed(file_path, hash_value)
        )

    def _is_changed(self, path: Path, new_hash: str) -> bool:
        """キャッシュと比較して変更検出"""
        old_hash = self.hash_cache.get(str(path))
        self.hash_cache[str(path)] = new_hash
        return old_hash != new_hash
```

#### 3.1.3 ファイルウォッチャー (`backend/watcher.py`)

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio

class ContentWatcher:
    def __init__(self, path: str, callback: Callable):
        self.path = path
        self.callback = callback
        self.observer = Observer()
        self._debounce_task: Optional[asyncio.Task] = None
        self._pending_events: list = []

    def start(self):
        handler = self._create_handler()
        self.observer.schedule(handler, self.path, recursive=True)
        self.observer.start()

    def _create_handler(self) -> FileSystemEventHandler:
        watcher = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                if event.src_path.endswith(('.html', '.txt', '.mp3')):
                    asyncio.create_task(watcher._debounced_callback(event))

        return Handler()

    async def _debounced_callback(self, event):
        """100msデバウンス"""
        self._pending_events.append(event)

        if self._debounce_task:
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(self._flush_events())

    async def _flush_events(self):
        await asyncio.sleep(0.1)  # 100ms待機
        events = self._pending_events.copy()
        self._pending_events.clear()
        await self.callback(events)
```

#### 3.1.4 WebSocket接続プール (`backend/websocket.py`)

```python
from fastapi import WebSocket
from typing import Set
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, event: str, data: dict):
        """全クライアントに送信"""
        message = json.dumps({"event": event, "data": data})
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)

        # 切断された接続を削除
        self.active_connections -= disconnected

    async def send_personal(self, websocket: WebSocket, event: str, data: dict):
        """個別送信"""
        message = json.dumps({"event": event, "data": data})
        await websocket.send_text(message)
```

### 3.2 フロントエンドコンポーネント

#### 3.2.1 状態管理

```javascript
// frontend/store.js
const { reactive, readonly, provide, inject } = Vue;

const createStore = () => {
  const state = reactive({
    projects: [],
    selectedProject: null,
    isLoading: false,
    wsConnected: false,
    lastUpdated: null
  });

  const actions = {
    async fetchProjects() {
      state.isLoading = true;
      try {
        const response = await fetch('/api/projects');
        state.projects = await response.json();
        state.lastUpdated = new Date();
      } finally {
        state.isLoading = false;
      }
    },

    updateProject(project) {
      const index = state.projects.findIndex(p => p.id === project.id);
      if (index !== -1) {
        state.projects[index] = project;
      }
    },

    setWsConnected(connected) {
      state.wsConnected = connected;
    }
  };

  return { state: readonly(state), actions };
};

const StoreSymbol = Symbol('store');

export const provideStore = (app) => {
  const store = createStore();
  app.provide(StoreSymbol, store);
};

export const useStore = () => inject(StoreSymbol);
```

#### 3.2.2 WebSocketサービス

```javascript
// frontend/services/websocket.js
class WebSocketService {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.handlers = new Map();
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.emit('connected');
    };

    this.ws.onmessage = (event) => {
      const { event: eventType, data } = JSON.parse(event.data);
      this.emit(eventType, data);
    };

    this.ws.onclose = () => {
      this.emit('disconnected');
      this.attemptReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      const delay = Math.pow(2, this.reconnectAttempts) * 1000;
      setTimeout(() => {
        this.reconnectAttempts++;
        this.connect();
      }, delay);
    }
  }

  on(event, handler) {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event).push(handler);
  }

  emit(event, data) {
    const handlers = this.handlers.get(event) || [];
    handlers.forEach(handler => handler(data));
  }
}

export const wsService = new WebSocketService(
  `ws://${window.location.host}/ws`
);
```

#### 3.2.3 ダッシュボードコンポーネント

```javascript
// frontend/components/Dashboard.js
const Dashboard = {
  template: `
    <div class="container mx-auto px-4 py-8">
      <!-- ヘッダーサマリー -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-gray-500 text-sm">全プロジェクト</h3>
          <p class="text-3xl font-bold">{{ stats.totalProjects }}</p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-gray-500 text-sm">全体進捗</h3>
          <p class="text-3xl font-bold text-blue-600">{{ stats.overallProgress }}%</p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-gray-500 text-sm">完了トピック</h3>
          <p class="text-3xl font-bold text-green-600">{{ stats.completedTopics }}</p>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-gray-500 text-sm">最終更新</h3>
          <p class="text-lg">{{ formattedLastUpdate }}</p>
        </div>
      </div>

      <!-- アクションバー -->
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold">プロジェクト一覧</h2>
        <button
          @click="triggerScan"
          :disabled="isScanning"
          class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg flex items-center gap-2"
        >
          <span v-if="isScanning" class="animate-spin">⟳</span>
          {{ isScanning ? 'スキャン中...' : '手動スキャン' }}
        </button>
      </div>

      <!-- プロジェクトカード -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <ProjectCard
          v-for="project in projects"
          :key="project.id"
          :project="project"
          @select="selectProject"
        />
      </div>
    </div>
  `,

  setup() {
    const { state, actions } = useStore();
    const isScanning = ref(false);

    const stats = computed(() => ({
      totalProjects: state.projects.length,
      overallProgress: calculateOverallProgress(state.projects),
      completedTopics: state.projects.reduce(
        (sum, p) => sum + p.completed_topics, 0
      )
    }));

    const triggerScan = async () => {
      isScanning.value = true;
      try {
        await fetch('/api/scan', { method: 'POST' });
      } finally {
        isScanning.value = false;
      }
    };

    return { state, stats, isScanning, triggerScan };
  }
};
```

---

## 4. データフロー

### 4.1 起動時フロー

```
1. uvicorn 起動
2. FastAPI アプリ初期化
3. SQLite 接続（WALモード有効化）
4. ファイルウォッチャー起動
5. 初回フルスキャン（バックグラウンド）
6. 静的ファイルサーバー起動
7. WebSocket 待受開始
```

### 4.2 リアルタイム更新フロー

```
[ファイル変更発生]
        ↓
[watchdog検出]
        ↓ イベント
[デバウンス処理 (100ms)]
        ↓
[差分スキャン実行]
        ↓
[SQLite 更新]
        ↓
[WebSocket broadcast]
        ↓
[Vue.js state 更新]
        ↓
[UI リアクティブ更新]
```

### 4.3 API リクエストフロー

```
[クライアント]
     ↓ fetch
[FastAPI Router]
     ↓
[Service Layer]
     ↓
[aiosqlite クエリ]
     ↓
[JSON レスポンス]
     ↓
[クライアント]
```

---

## 5. ディレクトリ構造

```
training-content-progress-tracker-agent/
├── worktrees/phase1-planning-b/
│   ├── REQUIREMENTS.md
│   ├── WBS.json
│   ├── CRITICAL_PATH.md
│   └── ARCHITECTURE.md
│
└── project/
    ├── backend/
    │   ├── __init__.py
    │   ├── main.py              # FastAPI アプリエントリーポイント
    │   ├── config.py            # 設定管理
    │   ├── database.py          # DB接続・初期化
    │   ├── models.py            # Pydantic モデル
    │   ├── scanner.py           # 非同期ファイルスキャナー
    │   ├── watcher.py           # ファイルウォッチャー
    │   ├── wbs_parser.py        # WBSパーサー（両形式対応）
    │   ├── websocket.py         # WebSocket接続管理
    │   └── routers/
    │       ├── __init__.py
    │       ├── projects.py      # /api/projects
    │       ├── topics.py        # /api/topics
    │       └── scan.py          # /api/scan
    │
    ├── frontend/
    │   ├── index.html           # SPA エントリーポイント
    │   ├── app.js               # Vue.js アプリ
    │   ├── store.js             # 状態管理
    │   ├── components/
    │   │   ├── Dashboard.js
    │   │   ├── ProjectCard.js
    │   │   ├── ProjectDetail.js
    │   │   ├── TopicList.js
    │   │   └── ProgressChart.js
    │   └── services/
    │       ├── api.js
    │       └── websocket.js
    │
    ├── tests/
    │   ├── unit/
    │   │   ├── test_wbs_parser.py
    │   │   ├── test_scanner.py
    │   │   └── test_api.py
    │   ├── integration/
    │   │   └── test_full_flow.py
    │   └── e2e/
    │       └── test_dashboard.py
    │
    ├── data/
    │   └── progress_tracker.db  # SQLite DB
    │
    ├── requirements.txt
    ├── launch_app.command
    └── README.md
```

---

## 6. セキュリティ考慮

### 6.1 ローカル実行前提

- 外部公開なし（localhost のみ）
- 認証不要（シングルユーザー）
- CORS 設定なし

### 6.2 ファイルアクセス

- 読み取り専用（ファイル変更なし）
- 対象フォルダ外へのアクセス禁止
- パストラバーサル対策

---

## 7. パフォーマンス最適化

### 7.1 バックエンド

| 最適化 | 効果 |
|-------|-----|
| aiosqlite | I/O待ちをブロックしない |
| xxhash | ハッシュ計算10倍高速 |
| WALモード | 読み書き並行 |
| デバウンス | 連続イベント集約 |
| メモリキャッシュ | 差分検出高速化 |

### 7.2 フロントエンド

| 最適化 | 効果 |
|-------|-----|
| CDN | ビルド不要、キャッシュ活用 |
| 仮想スクロール | 大量トピック対応 |
| computed | 不要な再計算回避 |
| WebSocket | ポーリング不要 |

---

## 8. 拡張性

### 8.1 将来の拡張ポイント

| 機能 | 実装方針 |
|-----|---------|
| PWA対応 | Service Worker 追加 |
| 進捗予測 | 履歴データから移動平均 |
| 通知 | Web Notifications API |
| エクスポート | CSV/JSON 出力API追加 |
| マルチフォルダ | config.yamlで複数パス対応 |

### 8.2 プラグインアーキテクチャ（将来）

```python
# 将来の拡張用インターフェース
class ScannerPlugin(Protocol):
    def scan(self, path: Path) -> ScanResult: ...

class NotificationPlugin(Protocol):
    def notify(self, event: Event) -> None: ...
```

---

## 9. まとめ

### 革新的アプローチの特徴

1. **イベント駆動**: ファイル変更を即座に検出・反映
2. **非同期処理**: asyncio 活用で高スループット
3. **リアルタイム通信**: WebSocket で低レイテンシ
4. **軽量実装**: CDN活用でビルド不要
5. **スケーラブル**: 仮想スクロールで大量データ対応

### 技術的優位性

- 初回スキャン: < 3秒（13プロジェクト）
- 差分検出: < 100ms
- UI更新: < 50ms（WebSocket経由）
- メモリ使用: < 256MB
