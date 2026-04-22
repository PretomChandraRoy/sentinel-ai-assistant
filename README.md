<div align="center">

# 🛡️ Sentinel AI Assistant

**A local-first AI desktop assistant that watches over your PC.**

Chat · Voice · System Monitoring · Smart Notifications · Task Tracking

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-000000?logo=ollama)](https://ollama.com)
[![PyQt6](https://img.shields.io/badge/PyQt6-UI-41cd52?logo=qt)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

*Your personal AI assistant that runs entirely on your machine —*
*no cloud, no subscriptions, no API keys needed.*

</div>

## ✨ Features

| Feature | Description |
|---|---|
| 🗣️ **Voice-First Assistant** | Continuous listening — just speak, Sentinel responds aloud. No buttons needed |
| 🤖 **AI Chat** | Context-aware assistant powered by local Ollama LLM — knows your tasks, system state, and activity |
| 🖥️ **System Monitor** | Real-time CPU, RAM, disk, battery, and active window tracking |
| 🔔 **Smart Alerts** | Proactive notifications for low battery, high CPU/RAM, and stuck tasks |
| 💬 **Proactive Check-ins** | AI asks you questions — suggests breaks, reminds deadlines, offers help every 30 min |
| 📋 **Task Tracking** | Full task lifecycle with deadlines, overdue alerts, and project organization |
| 🔄 **Session Restore** | On launch, reopens apps you had running last time + shows what you were working on |
| ⏰ **Deadline Tracking** | Set due dates on tasks — overdue warnings, upcoming deadline briefings |
| 🌅 **Startup Briefing** | Spoken welcome with task summary, deadlines, and workspace restoration |
| 🔄 **Integrations** | Auto-sync from Git commits, Jira issues, file changes, and browser tabs |
| 🌐 **Web Dashboard** | HTML dashboard + REST API for remote access |
| 🔒 **Privacy-First** | 100% local — SQLite storage, no data leaves your machine |

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** with pip
- **[Ollama](https://ollama.com)** installed and running
- **Windows 10/11** (system tray + voice features are Windows-native)

### Installation

```powershell
# 1. Clone the repo
git clone https://github.com/PretomChandraRoy/sentinel-ai-assistant.git
cd sentinel-ai-assistant

# 2. Create virtual environment & install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

# 3. Pull an AI model (if you haven't already)
ollama pull qwen3.5:9b
```

### Launch

```powershell
python -m agent_app.cli jarvis
```

A system tray icon (🔵) appears → **left-click** to open the chat window.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                System Tray (pystray)              │
│                                                    │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐ │
│  │  Chat GUI  │  │  Voice I/O │  │   Notifier   │ │
│  │  (PyQt6)   │  │  (STT/TTS) │  │  (Toasts)   │ │
│  └─────┬──────┘  └─────┬──────┘  └──────┬──────┘ │
│        └────────────────┼────────────────┘        │
│                         ▼                         │
│               ┌─────────────────┐                 │
│               │    AI Brain     │                 │
│               │   (Ollama)      │                 │
│               └────────┬────────┘                 │
│                        ▼                          │
│  ┌──────────────────────────────────────────────┐ │
│  │             Context Engine                    │ │
│  │  Tasks · System Stats · Activity · Browser   │ │
│  └──────────────────────────────────────────────┘ │
│                        ▼                          │
│  ┌──────────────────────────────────────────────┐ │
│  │  FastAPI Server + Sync Orchestrator           │ │
│  │  Jira · Git · Workfiles · Browser · Webhooks │ │
│  └──────────────────────────────────────────────┘ │
│                     SQLite DB                     │
└──────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
src/agent_app/
├── tray.py                  # Main app — orchestrates all components
├── cli.py                   # CLI entry point
├── config.py                # Environment-based settings
├── models.py                # Data models (Task, Status)
├── core/
│   ├── brain.py             # AI brain (Ollama integration)
│   ├── orchestrator.py      # Sync scheduler (startup + polling)
│   ├── sync.py              # Integration sync service
│   ├── retry_queue.py       # Retry failed writes with backoff
│   └── credentials.py       # OS keyring credential store
├── gui/
│   └── chat_window.py       # PyQt6 dark-themed chat UI
├── monitors/
│   ├── system_monitor.py    # CPU, RAM, disk, battery, active window
│   └── notifier.py          # Windows toast notifications
├── voice/
│   ├── listener.py          # Speech recognition (Google free API)
│   └── speaker.py           # Text-to-speech (pyttsx3)
├── dashboard/
│   ├── api.py               # FastAPI routes + REST API
│   └── templates/           # Jinja2 HTML templates
├── db/
│   └── repository.py        # SQLite operations (10 tables)
└── integrations/
    ├── base.py              # Adapter protocol
    ├── jira.py              # Jira read/write (real API)
    ├── github_issues.py     # GitHub Issues (read-only)
    ├── git.py               # Git commit ingestion
    ├── workfiles.py         # File change detection
    └── browser.py           # Browser tab tracking
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Send a message to the AI |
| `/api/system/status` | GET | Real-time system stats |
| `/api/chat/history` | GET | Conversation history |
| `/api/notifications` | GET | Unread notifications |
| `/api/tasks` | GET/POST | List or create tasks (supports `deadline` field) |
| `/api/tasks/{id}/status` | POST | Update task status |
| `/api/tasks/{id}/deadline` | POST | Set or clear a task deadline |
| `/api/tasks/upcoming` | GET | Tasks with deadlines in the next N days + overdue |
| `/api/summary` | GET | Dashboard summary |
| `/api/sync/trigger` | POST | Trigger manual sync |
| `/dashboard` | GET | Web dashboard (HTML) |

## ⌨️ CLI Commands

```powershell
python -m agent_app.cli jarvis          # Launch Sentinel (voice-first mode)
python -m agent_app.cli init-db         # Initialize database
python -m agent_app.cli create-task "Fix login bug"
python -m agent_app.cli create-task "Deploy v2" --deadline 2026-04-20
python -m agent_app.cli list-tasks
python -m agent_app.cli set-status 1 done
python -m agent_app.cli sync-once       # One-time sync from all sources
python -m agent_app.cli serve           # Run web server only
```

## 🧪 Tests

```powershell
python -m pytest tests -v
```

```
14 passed ✅
├── test_api.py                  (2 integration tests)
├── test_brain.py                (3 tests — context, fallback, history)
├── test_system_monitor.py       (2 tests — snapshot, dict conversion)
├── test_voice.py                (3 tests — mute toggle, set, speak guard)
├── test_repository.py           (3 tests — lifecycle, counts, jira link)
└── test_git_adapter.py          (1 test — log parsing)
```

## 🔧 Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `AGENT_WORKSPACE_ROOT` | Current directory | Root folder to monitor |
| `AGENT_DB_PATH` | `.agentforpc.db` | SQLite database path |
| `AGENT_POLLING_SECONDS` | `900` (15 min) | Sync polling interval |
| `JIRA_BASE_URL` | — | Jira instance URL |
| `JIRA_EMAIL` | — | Jira account email |
| `JIRA_API_TOKEN` | — | Jira API token |

## 🗺️ Roadmap

- [x] System tray app with PyQt6 chat window
- [x] Local AI brain (Ollama)
- [x] System monitoring & proactive alerts
- [x] Voice interaction (STT + TTS)
- [x] Continuous voice listening (voice-first mode)
- [x] Task tracking with Jira sync
- [x] Deadline tracking & overdue alerts
- [x] Session restore (reopen apps on launch)
- [x] Startup briefing (spoken + visual)
- [x] Proactive AI check-ins (asks questions)
- [x] App launch & control
- [x] Screen content awareness (OCR via Windows native engine)
- [x] AI Memory / RAG (ChromaDB — remembers everything across sessions)
- [ ] Clipboard monitoring
- [ ] Calendar integration
- [x] Learning user patterns over time (app usage, productive hours, focus score)

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">

**Built with 💜 by [Pretom Chandra Roy](https://github.com/PretomChandraRoy)**

</div>
