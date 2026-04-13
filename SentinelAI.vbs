Set WshShell = CreateObject("WScript.Shell")
' Get the directory where this script lives
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonExe = scriptDir & "\.venv\Scripts\pythonw.exe"
' Run JARVIS silently (no console window)
WshShell.Run """" & pythonExe & """ -m agent_app.cli jarvis", 0, False
