"""Configure MAY AI Assistant to run on Windows Startup."""
import os
import sys
from pathlib import Path

def get_startup_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

def is_startup_enabled() -> bool:
    startup_dir = get_startup_dir()
    vbs_path = startup_dir / "MAY_Assistant.vbs"
    bat_path = startup_dir / "MAY_Assistant.bat"
    return vbs_path.is_file() or bat_path.is_file()

def enable_startup() -> bool:
    project_dir = Path(__file__).resolve().parent
    startup_dir = get_startup_dir()
    startup_dir.mkdir(parents=True, exist_ok=True)
    vbs_path = startup_dir / "MAY_Assistant.vbs"
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        f'projectDir = "{project_dir}"\n'
        'pythonwPath = projectDir & "\\.venv\\Scripts\\pythonw.exe"\n'
        'scriptPath = projectDir & "\\may_assistant.py"\n'
        'If Not fso.FileExists(pythonwPath) Then\n'
        '    MsgBox "MAY Python runtime was not found: " & pythonwPath, vbExclamation, "MAY"\n'
        '    WScript.Quit 1\n'
        'End If\n'
        'If Not fso.FileExists(scriptPath) Then\n'
        '    MsgBox "MAY program was not found: " & scriptPath, vbExclamation, "MAY"\n'
        '    WScript.Quit 1\n'
        'End If\n'
        'WshShell.CurrentDirectory = projectDir\n'
        'WshShell.Run """" & pythonwPath & """ """ & scriptPath & """ --startup", 0, False\n'
    )
    vbs_path.write_text(vbs_content, encoding="utf-8")
    print(f"[OK] MAY enabled on Windows startup: {vbs_path}")
    return True

def disable_startup() -> bool:
    startup_dir = get_startup_dir()
    for name in ("MAY_Assistant.vbs", "MAY_Assistant.bat"):
        path = startup_dir / name
        if path.is_file():
            path.unlink()
            print(f"[OK] Removed startup shortcut: {path}")
    print("[OK] MAY disabled from Windows startup.")
    return True

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    if action == "enable":
        enable_startup()
    elif action == "disable":
        disable_startup()
    elif action == "toggle":
        if is_startup_enabled():
            disable_startup()
        else:
            enable_startup()
    else:
        status = "ENABLED" if is_startup_enabled() else "DISABLED"
        print(f"MAY Windows Startup Status: {status}")
        print("Usage: python setup_startup.py [enable|disable|toggle|status]")