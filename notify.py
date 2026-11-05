#!/usr/bin/env python3
r"""
Universal AI Agent Notifier for Telegram (Zero External Dependencies).

Mendukung 3 mode penggunaan:
1. Lifecycle Hook Mode (Otomatis untuk Google Antigravity & Claude Code):
   python "D:\ai-bot\notify.py" --hook --agent "Antigravity"
2. Direct Message Mode (Dari CLI / Script / Custom Agent):
   python "D:\ai-bot\notify.py" --agent "Cursor" --message "Refactor selesai!"
3. Command Wrapper Mode (Membungkus perintah CLI apapun):
   python "D:\ai-bot\notify.py" --run agy -p "Buat unit test"
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def load_env(env_path: Path = ENV_FILE) -> dict:
    """Membaca file .env tanpa memerlukan library python-dotenv."""
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip().strip('"').strip("'")
    return env_vars


def send_telegram_message(text: str, token: str = "", chat_id: str = "") -> bool:
    """Mengirim pesan ke Telegram menggunakan urllib bawaan Python."""
    env = load_env()
    bot_token = token or os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")
    target_chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID") or env.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or not target_chat_id:
        return False

    # Potong jika melebihi batas karakter Telegram (4096)
    if len(text) > 4000:
        text = text[:3950] + "\n\n... (pesan dipotong)"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": text,
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def extract_last_assistant_reply(transcript_path: str) -> str:
    """Mencoba mengambil ringkasan jawaban terakhir AI dari file transcript.jsonl."""
    if not transcript_path:
        return ""
    path = Path(transcript_path)
    if not path.exists():
        return ""

    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            if not line.strip():
                continue
            obj = json.loads(line)
            # Format transcript Antigravity (PLANNER_RESPONSE) atau Claude
            step_type = obj.get("type", "")
            content = obj.get("content", "")
            if step_type == "PLANNER_RESPONSE" and content and not obj.get("tool_calls"):
                return str(content).strip()
            if obj.get("role") == "assistant" and isinstance(content, str) and content.strip():
                return content.strip()
    except Exception:
        pass
    return ""


def handle_hook(default_agent_name: str = "AI Agent") -> None:
    """
    Membaca JSON payload dari stdin saat dipanggil oleh Lifecycle Stop Hook
    (Google Antigravity / Claude Code), mengirim notifikasi ke Telegram,
    dan mengembalikan JSON {} ke stdout sesuai kontrak hook.
    """
    raw_stdin = ""
    try:
        if not sys.stdin.isatty():
            raw_stdin = sys.stdin.read()
    except Exception:
        pass

    payload = {}
    if raw_stdin.strip():
        try:
            payload = json.loads(raw_stdin)
        except Exception:
            payload = {}

    # Ekstrak informasi dari payload hook Antigravity / Claude Code
    workspace_list = payload.get("workspacePaths") or []
    workspace = workspace_list[0] if workspace_list else payload.get("cwd", os.getcwd())
    last_prompt = payload.get("lastUserInput") or payload.get("prompt") or "(Tidak ada detail prompt)"
    reason = payload.get("terminationReason") or payload.get("stop_hook_active") or "COMPLETED"
    error_text = payload.get("error") or ""
    model_name = payload.get("modelName") or ""
    transcript_path = payload.get("transcriptPath") or payload.get("transcript_path") or ""

    last_reply = extract_last_assistant_reply(transcript_path)
    if len(last_reply) > 700:
        last_reply = last_reply[:700] + "..."

    status_icon = "✅" if not error_text and reason != "ERROR" else "⚠️"
    lines = [
        f"{status_icon} [{default_agent_name}] Selesai Mengerjakan Prompt!",
        f"📂 Workspace: {workspace}",
    ]
    if model_name:
        lines.append(f"🧠 Model: {model_name}")
    lines.append(f"🏁 Status: {reason}")
    if error_text:
        lines.append(f"❌ Error: {error_text}")

    lines.append(f"\n💬 Prompt Terakhir:\n{last_prompt[:400]}")

    if last_reply:
        lines.append(f"\n📝 Ringkasan Jawaban:\n{last_reply}")

    send_telegram_message("\n".join(lines))

    # Kontrak output untuk Stop Hook Antigravity / Claude Code
    sys.stdout.write("{}\n")
    sys.stdout.flush()


def handle_wrapper(cmd_args: list, agent_name: str) -> int:
    """Menjalankan perintah CLI dan mengirim notifikasi ke Telegram setelah selesai."""
    if not cmd_args:
        print("Error: Perintah yang akan dijalankan kosong.", file=sys.stderr)
        return 1

    cmd_str = " ".join(cmd_args)
    cwd = os.getcwd()
    start_time = time.time()

    print(f"🚀 Menjalankan [{agent_name}]: {cmd_str}")
    try:
        proc = subprocess.run(cmd_args, shell=(os.name == "nt"))
        exit_code = proc.returncode
    except Exception as exc:
         duration = round(time.time() - start_time, 1)
         msg = (
             f"❌ [{agent_name}] Gagal Dijalankan ({duration}s)\n"
             f"📂 Folder: {cwd}\n"
             f"💻 Perintah: {cmd_str}\n"
             f"⚠️ Error: {exc}"
         )
         send_telegram_message(msg)
         return 1

    duration = round(time.time() - start_time, 1)
    icon = "✅" if exit_code == 0 else "⚠️"
    msg = (
        f"{icon} [{agent_name}] Selesai ({duration}s)\n"
        f"📂 Folder: {cwd}\n"
        f"💻 Perintah: {cmd_str}\n"
        f"🔢 Exit Code: {exit_code}"
    )
    send_telegram_message(msg)
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Universal AI Agent Telegram Notifier")
    parser.add_argument("--hook", action="store_true", help="Jalankan sebagai Lifecycle Stop Hook (baca JSON dari stdin)")
    parser.add_argument("--agent", default="AI Agent", help="Nama AI Agent pengirim notifikasi")
    parser.add_argument("--message", "-m", default="", help="Pesan notifikasi langsung")
    parser.add_argument("--run", nargs=argparse.REMAINDER, help="Jalankan perintah CLI dan kirim notifikasi saat selesai")

    args = parser.parse_args()

    if args.hook:
        handle_hook(args.agent)
        return

    if args.run is not None:
        code = handle_wrapper(args.run, args.agent)
        sys.exit(code)

    if args.message:
        cwd = os.getcwd()
        text = f"🔔 [{args.agent}] Notifikasi\n📂 Folder: {cwd}\n\n{args.message}"
        ok = send_telegram_message(text)
        if ok:
            print("✅ Notifikasi berhasil dikirim ke Telegram.")
        else:
            print("⚠️ Gagal mengirim notifikasi. Pastikan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di D:\\ai-bot\\.env sudah terisi.", file=sys.stderr)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
