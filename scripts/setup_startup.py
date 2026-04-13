"""Setup Sentinel AI as a Windows startup application.

Creates a shortcut in the Windows Startup folder so Sentinel launches
automatically when you log in. Run this script once:

    python scripts/setup_startup.py

To remove from startup:

    python scripts/setup_startup.py --remove
"""
import os
import sys
import argparse


def get_startup_folder() -> str:
    return os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )


def create_shortcut(target_path: str, shortcut_name: str = "SentinelAI") -> str:
    """Create a .lnk shortcut in the Windows Startup folder."""
    startup_dir = get_startup_folder()
    shortcut_path = os.path.join(startup_dir, f"{shortcut_name}.lnk")

    # Use PowerShell to create the shortcut (no extra dependencies needed)
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ps_script = f'''
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut("{shortcut_path}")
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = '"{target_path}"'
$shortcut.WorkingDirectory = "{project_dir}"
$shortcut.Description = "Sentinel AI Assistant"
$shortcut.Save()
'''
    os.system(f'powershell -Command "{ps_script}"')
    return shortcut_path


def remove_shortcut(shortcut_name: str = "SentinelAI") -> bool:
    startup_dir = get_startup_folder()
    shortcut_path = os.path.join(startup_dir, f"{shortcut_name}.lnk")
    if os.path.exists(shortcut_path):
        os.remove(shortcut_path)
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Sentinel AI startup")
    parser.add_argument("--remove", action="store_true", help="Remove from startup")
    args = parser.parse_args()

    if args.remove:
        if remove_shortcut():
            print("[OK] Removed Sentinel AI from startup.")
        else:
            print("[INFO] Sentinel AI was not in startup.")
        return

    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vbs_path = os.path.join(project_dir, "SentinelAI.vbs")

    if not os.path.exists(vbs_path):
        print(f"[ERROR] {vbs_path} not found!")
        sys.exit(1)

    shortcut_path = create_shortcut(vbs_path)
    print(f"[OK] Sentinel AI added to Windows startup!")
    print(f"   Shortcut: {shortcut_path}")
    print(f"   Target:   {vbs_path}")
    print(f"\n   It will launch automatically next time you log in.")
    print(f"   To remove: python scripts/setup_startup.py --remove")


if __name__ == "__main__":
    main()
