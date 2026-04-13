$ErrorActionPreference = "Stop"

$python = "D:\Documents\AgentForPC\.venv\Scripts\python.exe"
& $python -m agent_app.cli serve --host 127.0.0.1 --port 8000

