# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Documents\\AgentForPC\\sentinel_launcher.py'],
    pathex=['D:\\Documents\\AgentForPC\\src'],
    binaries=[],
    datas=[('D:\\Documents\\AgentForPC\\src\\agent_app\\dashboard\\templates', 'agent_app\\dashboard\\templates')],
    hiddenimports=['agent_app.tray', 'agent_app.gui.chat_window', 'agent_app.core.brain', 'agent_app.core.session_manager', 'agent_app.monitors.system_monitor', 'agent_app.monitors.notifier', 'agent_app.voice.listener', 'agent_app.voice.speaker', 'pystray._win32', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['comtypes', 'pyttsx3', 'speech_recognition'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SentinelAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SentinelAI',
)
