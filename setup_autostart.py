#!/usr/bin/env python3
"""
Mengatur Auto-Start Bot Telegram saat Windows menyala (Startup).
Berjalan di background secara silent (tanpa jendela hitam CMD) menggunakan pythonw.exe / VBScript.
"""

import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
BOT_SCRIPT = BASE_DIR / "bot.py"
ENV_FILE = BASE_DIR / ".env"

STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
VBS_PATH = STARTUP_DIR / "AI_Telegram_Bot_Autostart.vbs"


def install_autostart() -> None:
    if not STARTUP_DIR.exists():
        print(f"❌ Folder Startup Windows tidak ditemukan: {STARTUP_DIR}")
        sys.exit(1)

    # Gunakan VBScript wrapper agar berjalan 100% silent di background (WindowStyle = 0)
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{BASE_DIR}"
WshShell.Run "python ""{BOT_SCRIPT}""", 0, False
Set WshShell = Nothing
'''
    VBS_PATH.write_text(vbs_content, encoding="utf-8")
    print("=" * 65)
    print("✅ AUTO-START WINDOWS BERHASIL DIAKTIFKAN!")
    print("=" * 65)
    print(f"📄 File Startup : {VBS_PATH}")
    print("💡 Sekarang setiap kali laptop di-restart / dinyalakan,")
    print("   Bot Telegram akan otomatis berjalan di background (tanpa jendela CMD).")
    print("   Pastikan Anda sudah mengisi Bot Token minimal 1x lewat start_bot.bat.")
    print("=" * 65)


def remove_autostart() -> None:
    if VBS_PATH.exists():
        VBS_PATH.unlink()
        print(f"🛑 Auto-Start berhasil dihapus dari Startup Windows ({VBS_PATH}).")
    else:
        print("ℹ️ Auto-Start belum terpasang.")


if __name__ == "__main__":
    if "--disable" in sys.argv:
        remove_autostart()
    else:
        install_autostart()
