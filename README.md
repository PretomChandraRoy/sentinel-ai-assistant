# AgentForPC — JARVIS Edition

Local-first AI assistant for your PC, inspired by Iron Man's JARVIS.
System tray app with chat, voice, system monitoring, and proactive notifications.

## Quick Start (Windows PowerShell)

### 1. Install dependencies
```powershell
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m pip install -r D:\Documents\AgentForPC\requirements.txt
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m pip install -e D:\Documents\AgentForPC
```

### 2. Install Ollama (AI brain)
Download from https://ollama.com, then:
```powershell
ollama serve
ollama pull llama3.2:3b
```

### 3. Launch JARVIS
```powershell
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m agent_app.cli jarvis
```

A system tray icon (🔵 J) appears. Left-click to open the chat window.

## Features
- **🤖 AI Chat** — Context-aware assistant powered by local Ollama LLM
- **🖥️ System Monitor** — Real-time CPU, RAM, disk, battery tracking
- **🎤 Voice I/O** — Push-to-talk mic input + text-to-speech responses
- **🔔 Proactive Alerts** — Battery low, high CPU/RAM, stuck tasks
- **📋 Task Tracking** — Full task CRUD with Jira sync
- **🔄 Auto Sync** — Git, workfiles, browser activity ingestion
- **🌐 Web Dashboard** — Available at http://127.0.0.1:8000/dashboard (when using `serve`)

## CLI Commands
```powershell
# Launch JARVIS (system tray + chat)
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m agent_app.cli jarvis

# Original commands still work
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m agent_app.cli init-db
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m agent_app.cli create-task "Finish homework"
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m agent_app.cli list-tasks
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m agent_app.cli set-status 1 done
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m agent_app.cli sync-once
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m agent_app.cli serve --port 8000
```

## API Endpoints (new)
| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Send a message to the AI brain |
| `/api/system/status` | GET | Real-time system stats |
| `/api/chat/history` | GET | Conversation history |
| `/api/notifications` | GET | Unread notifications |

## Tray Menu
- **Open JARVIS** — Opens the chat window (also left-click the icon)
- **Sync Now** — Trigger manual sync from all sources
- **Voice > Mute/Unmute** — Toggle voice responses
- **Quit** — Saves a daily snapshot and exits

## Jira Integration
```powershell
$env:JIRA_BASE_URL = "https://your-domain.atlassian.net"
$env:JIRA_EMAIL = "you@example.com"
$env:JIRA_API_TOKEN = "your_api_token"
```

## Tests
```powershell
D:\Documents\AgentForPC\.venv\Scripts\python.exe -m pytest D:\Documents\AgentForPC\tests -v
```

## Architecture
```
System Tray (pystray)
├── Chat Window (tkinter) ←→ AI Brain (Ollama)
├── System Monitor (psutil) → Notifications (toast)
├── Voice Listener (SpeechRecognition) + Speaker (pyttsx3)
├── Sync Orchestrator → Integrations (Git, Jira, Workfiles, Browser)
└── SQLite Database (tasks, chat, system snapshots, notifications)
```
