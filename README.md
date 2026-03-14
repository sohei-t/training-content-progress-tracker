# Training Content Progress Tracker

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![SQLite](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A real-time dashboard application for monitoring training content production progress. It watches the file system for HTML, TXT, and MP3 file creation, calculates weighted completion metrics, and broadcasts updates instantly via WebSocket. Supports multi-project tracking, master data management, Firebase content publishing, and RAG indexing with Gemini embeddings.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [API Reference](#api-reference)
- [WebSocket Events](#websocket-events)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Training content production involves creating multiple deliverables per topic: HTML pages, TXT scripts, and MP3 audio files. Tracking completion across dozens of projects and hundreds of topics manually is error-prone and slow.

This application automates that process by:

1. **Scanning** project directories for content files (HTML, TXT, MP3)
2. **Watching** the file system in real time for new or changed files
3. **Calculating** weighted progress (HTML 40%, TXT 30%, MP3 30%) per project
4. **Broadcasting** updates instantly to all connected dashboard clients via WebSocket
5. **Publishing** completed content to Firebase/Firestore for distribution
6. **Indexing** content with Gemini API embeddings for RAG-based search

---

## Features

### Real-Time Progress Dashboard
- Weighted progress calculation per project (HTML 40%, TXT 30%, MP3 30%)
- Per-file-type progress breakdown (HTML, TXT, MP3 individually)
- Topic-level status tracking: not started, in progress, completed
- Global statistics: total projects, topics, and completion rates

### File System Monitoring
- Automatic detection of new and changed files using `watchdog`
- Debounced event processing (configurable, default 100ms) to prevent redundant scans
- Fast change detection with `xxhash` (xxh64) and LRU cache with TTL
- Concurrent project scanning with configurable semaphore (default: 4 parallel)
- Automatic cleanup of deleted projects from the database

### WebSocket Live Updates
- Instant broadcast of scan start/progress/completion events
- Real-time project update notifications on file changes
- Publish progress streaming with per-topic callbacks
- RAG indexing progress notifications
- Connection pool with configurable max connections (default: 50)
- Ping/pong heartbeat support

### Multi-Project Management
- Automatic project discovery from base content directory
- WBS (Work Breakdown Structure) JSON parsing for structured topic lists
- Fallback file-system-based topic detection when WBS is absent
- Episode number matching to resolve WBS-to-filename mismatches
- MP3 duration extraction via TinyTag metadata

### Master Data Management
- **Destinations** -- delivery target management with drag-and-drop reorder
- **TTS Engines** -- text-to-speech engine configuration
- **Publication Statuses** -- content publication state (draft, free, public)
- **Check Statuses** -- review progress tracking
- Per-project notes and settings assignment

### Content Publishing
- One-click publishing of project content to Firebase Firestore
- Background processing with real-time progress callbacks via WebSocket
- Access type determination based on publication status (draft, free, public)
- Topic ordering by level prefix (intro, basic, intermediate, advanced)

### RAG Indexing
- Embedding generation using Gemini API (`gemini-embedding-001`)
- Batch processing with configurable batch size (default: 5)
- API key rotation for rate-limit resilience
- JSON-based index output (`rag_index.json`) per project
- Real-time build progress via WebSocket

---

## Architecture

```
+-------------------+         WebSocket (ws://)         +-------------------+
|                   | <-------------------------------> |                   |
|   Vue.js 3 SPA   |         REST API (HTTP)           |   FastAPI Backend |
|   + Tailwind CSS  | <-------------------------------> |   (async/await)   |
|                   |                                   |                   |
+-------------------+                                   +--------+----------+
                                                                 |
                                    +----------------------------+----------------------------+
                                    |                            |                            |
                             +------v------+            +--------v--------+          +--------v--------+
                             |   Scanner   |            |    Watcher      |          |   Database      |
                             |  (xxhash +  |            |  (watchdog +    |          |  (aiosqlite     |
                             |  LRU cache) |            |   debounce)     |          |   WAL mode)     |
                             +------+------+            +--------+--------+          +-----------------+
                                    |                            |
                                    v                            v
                          +-------------------+        +-------------------+
                          |  File System      |        |  File System      |
                          |  (content dirs)   |        |  (inotify/kqueue) |
                          +-------------------+        +-------------------+

                             +------------------+       +------------------+
                             | Publish Service  |       |   RAG Service    |
                             | (Firebase Admin) |       | (Gemini API)     |
                             +--------+---------+       +--------+---------+
                                      |                          |
                                      v                          v
                             +------------------+       +------------------+
                             |    Firestore     |       |  rag_index.json  |
                             +------------------+       +------------------+
```

### Data Flow

1. **Startup**: The application performs an initial full scan of all project directories, parsing WBS files and detecting content files.
2. **Watching**: The `watchdog` observer monitors the base content directory recursively. File events (create, modify, delete) are debounced and dispatched per project.
3. **Scanning**: The `AsyncScanner` uses `xxhash` for fast content hashing. Hashes are cached with TTL to detect changes efficiently. Projects are scanned concurrently.
4. **Broadcasting**: Every scan result or file change triggers a WebSocket broadcast to all connected dashboard clients.
5. **Publishing**: Content is uploaded to Firebase Firestore in the background, with per-topic progress streamed via WebSocket.
6. **RAG Indexing**: Text chunks are embedded using the Gemini API in batches, with API key rotation for throughput.

---

## Tech Stack

### Backend

| Component | Technology | Purpose |
|---|---|---|
| Web Framework | FastAPI 0.115+ | Async HTTP and WebSocket server |
| ASGI Server | uvicorn (with uvloop) | High-performance async server |
| Database | aiosqlite (WAL mode) | Async SQLite with optimized PRAGMAs |
| File Watching | watchdog 4.0+ | OS-level file system monitoring |
| Hashing | xxhash 3.4+ | Fast non-cryptographic file hashing |
| Validation | Pydantic v2 | Request/response data validation |
| Async I/O | aiofiles 24.1+ | Non-blocking file operations |
| Audio Metadata | tinytag 1.10+ | MP3 duration extraction |
| Firebase | firebase-admin 6.0+ | Firestore content publishing |
| HTTP Client | httpx 0.27+ | Async HTTP requests |
| Embeddings | google-generativeai 0.8+ | Gemini API for RAG indexing |
| Configuration | python-dotenv 1.0+ | Environment variable loading |

### Frontend

| Component | Technology | Purpose |
|---|---|---|
| UI Framework | Vue.js 3 (CDN) | Reactive single-page application |
| Styling | Tailwind CSS | Utility-first responsive design |
| Real-Time | WebSocket API | Live dashboard updates |

### Database Optimizations

The SQLite database uses several performance PRAGMAs:

```sql
PRAGMA journal_mode=WAL;         -- Write-Ahead Logging for concurrent reads
PRAGMA synchronous=NORMAL;       -- Balanced durability/performance
PRAGMA cache_size=10000;         -- 10,000 page cache (~40MB)
PRAGMA temp_store=MEMORY;        -- In-memory temp tables
PRAGMA mmap_size=268435456;      -- 256MB memory-mapped I/O
```

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- pip (Python package manager)
- A content directory containing project folders with `WBS.json` or `content/` subdirectories

### Installation

```bash
# Clone the repository
git clone https://github.com/sohei-t/training-content-progress-tracker.git
cd training-content-progress-tracker/project

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Quick Start

```bash
# Option 1: Use the launcher script (macOS)
./launch_app.command

# Option 2: Start manually
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

Open your browser at [http://localhost:8765](http://localhost:8765).

### Optional: Firebase Publishing Setup

To enable content publishing to Firebase Firestore:

1. Place your Firebase service account key at `~/.config/ai-agents/credentials/firebase/default.json`
2. Set environment variables in `~/.config/ai-agents/profiles/default.env`:
   ```
   FIREBASE_PROJECT_ID=your-project-id
   ```

### Optional: RAG Indexing Setup

To enable RAG indexing with Gemini embeddings:

1. Set one or more Gemini API keys in `~/.config/ai-agents/profiles/default.env`:
   ```
   GEMINI_API_KEY=your-api-key
   GEMINI_API_KEY_1=your-api-key-1
   GEMINI_API_KEY_2=your-api-key-2
   ```
2. Place a `rag_chunks.json` file in the project directory with pre-chunked content.

---

## Usage

1. **Dashboard** -- View aggregated progress across all projects on the home screen.
2. **Project Detail** -- Click a project card to see per-topic file completion status.
3. **Manual Scan** -- Trigger a full or per-project rescan from the dashboard.
4. **Settings** -- Manage destinations, TTS engines, publication statuses, and check statuses.
5. **Publish** -- Push completed content to Firebase Firestore with real-time progress.
6. **RAG Build** -- Generate embedding-based search indexes for project content.

---

## API Reference

All endpoints are prefixed with `/api`.

### Projects

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/projects` | List all projects with progress metrics |
| `GET` | `/api/projects/{id}` | Get project details with weighted progress |
| `GET` | `/api/projects/{id}/topics` | List topics with per-file completion status |
| `PUT` | `/api/projects/{id}/settings` | Update project settings (destination, TTS engine, etc.) |

### Scanning

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/scan` | Trigger a background scan (full or per-project) |
| `POST` | `/api/force-scan` | Force full scan with cache clear (development) |

**Scan Request Body:**
```json
{
  "project_id": null,
  "scan_type": "full"
}
```
- `project_id` (optional): Target a specific project. Omit or set `null` for all projects.
- `scan_type`: `"full"` or `"diff"`.

### Statistics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stats` | Get global statistics (projects, topics, progress) |

### Content Publishing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/projects/{id}/publish` | Publish project content to Firebase (background) |

### RAG Indexing

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/projects/{id}/rag-status` | Get RAG index status for a project |
| `POST` | `/api/projects/{id}/rag-build` | Build RAG index with Gemini embeddings (background) |
| `DELETE` | `/api/projects/{id}/rag-index` | Delete RAG index for a project |

### Master Data -- Destinations

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/destinations` | List all destinations |
| `POST` | `/api/destinations` | Create a new destination |
| `PUT` | `/api/destinations/{id}` | Update a destination |
| `PUT` | `/api/destinations/reorder` | Reorder destinations by ID list |
| `DELETE` | `/api/destinations/{id}` | Delete a destination |

### Master Data -- TTS Engines

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/tts-engines` | List all TTS engines |
| `POST` | `/api/tts-engines` | Create a new TTS engine |
| `PUT` | `/api/tts-engines/{id}` | Update a TTS engine |
| `PUT` | `/api/tts-engines/reorder` | Reorder TTS engines by ID list |
| `DELETE` | `/api/tts-engines/{id}` | Delete a TTS engine |

### Master Data -- Publication Statuses

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/publication-statuses` | List all publication statuses |
| `POST` | `/api/publication-statuses` | Create a new publication status |
| `PUT` | `/api/publication-statuses/{id}` | Update a publication status |
| `PUT` | `/api/publication-statuses/reorder` | Reorder publication statuses by ID list |
| `DELETE` | `/api/publication-statuses/{id}` | Delete a publication status |

### Master Data -- Check Statuses

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/check-statuses` | List all check statuses |
| `POST` | `/api/check-statuses` | Create a new check status |
| `PUT` | `/api/check-statuses/{id}` | Update a check status |
| `PUT` | `/api/check-statuses/reorder` | Reorder check statuses by ID list |
| `DELETE` | `/api/check-statuses/{id}` | Delete a check status |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check with timestamp |

---

## WebSocket Events

Connect to `ws://localhost:8765/ws` to receive real-time events.

### Connection

| Event | Direction | Description |
|---|---|---|
| `connected` | Server -> Client | Sent on successful connection with client count |
| `ping` / `pong` | Bidirectional | Heartbeat mechanism (send `"ping"` text, receive `pong` event) |

### Scan Events

| Event | Direction | Payload |
|---|---|---|
| `scan_started` | Server -> Client | `{ scan_id, project_id, type }` |
| `scan_progress` | Server -> Client | `{ scan_id, progress, current }` |
| `scan_completed` | Server -> Client | `{ scan_id, result: { projects_scanned, files_scanned, changes_detected } }` |

### Project Events

| Event | Direction | Payload |
|---|---|---|
| `project_updated` | Server -> Client | `{ project: { id, name, progress, html_count, txt_count, mp3_count, ... } }` |
| `topic_changed` | Server -> Client | `{ project_id, topic: { base_name, has_html, has_txt, has_mp3, status } }` |

### Publish Events

| Event | Direction | Payload |
|---|---|---|
| `publish_started` | Server -> Client | `{ project_id, project_name, total_topics }` |
| `publish_progress` | Server -> Client | `{ project_id, current, total, title }` |
| `publish_completed` | Server -> Client | `{ project_id, project_name, success, classroom_id, uploaded, total, errors }` |

### RAG Events

| Event | Direction | Payload |
|---|---|---|
| `rag_build_progress` | Server -> Client | `{ project_id, current, total, message, completed?, error? }` |

### Message Format

All WebSocket messages are JSON with the following structure:

```json
{
  "event": "event_name",
  "data": { ... },
  "timestamp": "2024-01-15T10:30:00.000000"
}
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `FIREBASE_PROJECT_ID` | Firebase project ID for content publishing | -- |
| `GEMINI_API_KEY` | Default Gemini API key for RAG indexing | -- |
| `GEMINI_API_KEY_1` ... `GEMINI_API_KEY_9` | Rotating Gemini API keys for rate-limit resilience | -- |

Environment variables are loaded from `~/.config/ai-agents/profiles/default.env`.

### Application Constants

| Constant | Location | Default | Description |
|---|---|---|---|
| `DEFAULT_CONTENT_PATH` | `main.py` | `~/Learning-Curricula` | Base directory for project content |
| `DEBOUNCE_MS` | `watcher.py` | `100` | File event debounce interval in milliseconds |
| `MAX_HASH_CACHE_SIZE` | `scanner.py` | `1000` | Maximum entries in the xxhash LRU cache |
| `HASH_TTL_SECONDS` | `scanner.py` | `300` | TTL for cached file hashes (5 minutes) |
| `BATCH_SIZE` | `rag_service.py` | `5` | Embedding batch size for Gemini API |
| `RATE_LIMIT_WAIT` | `rag_service.py` | `1.5` | Seconds to wait between embedding batches |
| `max_connections` | `websocket.py` | `50` | Maximum concurrent WebSocket connections |

### Progress Weights

File type weights for overall progress calculation:

| File Type | Weight | Description |
|---|---|---|
| HTML | 40% | Presentation/content pages |
| TXT | 30% | Audio scripts |
| MP3 | 30% | Generated audio files |

A topic is marked **completed** when all three file types (HTML, TXT, MP3) are present.

---

## Project Structure

```
training-content-progress-tracker/
├── LICENSE
├── README.md
└── project/
    ├── launch_app.command          # One-click launcher (macOS)
    ├── requirements.txt            # Python dependencies
    ├── backend/
    │   ├── __init__.py             # Package init
    │   ├── main.py                 # FastAPI app, lifespan, WebSocket endpoint
    │   ├── api.py                  # REST API routes (projects, scan, master data, publish, RAG)
    │   ├── database.py             # Async SQLite with WAL mode, all DB operations
    │   ├── scanner.py              # File scanner with xxhash, LRU cache, WBS parsing
    │   ├── watcher.py              # File system watcher with watchdog + debounce
    │   ├── websocket.py            # WebSocket connection manager with broadcasting
    │   ├── models.py               # Pydantic v2 request/response models
    │   ├── wbs_parser.py           # WBS.json parser with format detection
    │   ├── publish_service.py      # Firebase Firestore publishing service
    │   └── rag_service.py          # RAG index builder with Gemini embeddings
    ├── frontend/
    │   ├── index.html              # Main SPA page
    │   ├── css/
    │   │   └── styles.css          # Custom styles
    │   └── js/
    │       ├── app.js              # Vue.js 3 application
    │       ├── api.js              # HTTP API client
    │       └── websocket.js        # WebSocket client with auto-reconnect
    └── public/
        ├── index.html              # Portfolio/landing page
        └── about.html              # About page
```

---

## Testing

The project uses pytest with async support.

```bash
cd project

# Run all tests
pytest

# Run with coverage report
pytest --cov=backend --cov-report=html

# Run async tests only
pytest -m asyncio

# Run with verbose output
pytest -v
```

### Test Dependencies

Test dependencies are included in `requirements.txt`:

- `pytest` 8.0+ -- Test runner
- `pytest-asyncio` 0.23+ -- Async test support
- `pytest-cov` 4.0+ -- Coverage reporting
- `httpx` 0.27+ -- Async test client for FastAPI

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Follow the commit message convention: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
4. Ensure all tests pass: `pytest`
5. Submit a pull request

### Commit Message Examples

```
feat: add content publishing to Personal Video Platform with real-time progress
fix: remove hardcoded Firebase API key from publish_service.py
refactor: optimize scanner with stale cleanup and WBS resolution
docs: add comprehensive English README with API reference
```

---

## License

This project is licensed under the [MIT License](LICENSE).
