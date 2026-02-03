# Training Content Progress Tracker

A real-time dashboard application for visualizing training content production progress.

## Demo

- **Live App**: [index.html](./index.html)
- **About Page**: [about.html](./about.html)
- **Audio Explanation**: [explanation.mp3](./explanation.mp3) (Japanese)

## Features

- Real-time progress updates via WebSocket
- Multi-project management
- Topic tracking (HTML/TXT/MP3)
- Color-coded progress visualization
- Automatic file system monitoring

## Technology Stack

### Backend
- Python 3.12+ / FastAPI
- uvicorn (ASGI Server)
- aiosqlite (Async SQLite)
- watchdog (File System Monitoring)

### Frontend
- Vue.js 3
- Tailwind CSS
- WebSocket

## Quick Start

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `./launch_app.command`
4. Open http://localhost:8000

## Screenshots

```
+--------------------------------------------------+
|  Training Content Progress Tracker   [Live] [Scan]|
+--------------------------------------------------+
| [Total]  [Progress]  [Completed]  [Deliverables] |
|   12       78.5%       45/60         120         |
+--------------------------------------------------+
|  Project Cards with Progress Bars                |
|  - HTML (Green) / TXT (Blue) / MP3 (Orange)     |
+--------------------------------------------------+
```

## License

MIT License

---

Generated with Claude Code and AI Agent Workflow
