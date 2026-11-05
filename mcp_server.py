#!/usr/bin/env python3
"""
Universal MCP Server (Stdio JSON-RPC) untuk Notifikasi Telegram.
Bisa dipasang di Cursor, Windsurf, VS Code, Claude Desktop, dan Google Antigravity
agar AI Agent apa pun bisa memanggil tool `send_telegram_notification` saat selesai bekerja.
"""

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notify import send_telegram_message  # noqa: E402


def send_response(req_id, result):
    msg = {"jsonrpc": "2.0", "id": req_id, "result": result}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def send_error(req_id, code, message):
    msg = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        if method == "initialize":
            send_response(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "telegram-ai-notifier", "version": "1.0.0"},
                },
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            send_response(
                req_id,
                {
                    "tools": [
                        {
                            "name": "send_telegram_notification",
                            "description": "Kirim notifikasi ke HP pengguna melalui Telegram setelah AI Agent selesai mengerjakan prompt atau butuh konfirmasi.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_name": {
                                        "type": "string",
                                        "description": "Nama AI Agent (contoh: Cursor, Windsurf, Antigravity, Claude)",
                                    },
                                    "summary": {
                                        "type": "string",
                                        "description": "Ringkasan hasil pekerjaan yang baru saja diselesaikan",
                                    },
                                },
                                "required": ["summary"],
                            },
                        }
                    ]
                },
            )
        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments") or {}
            if tool_name == "send_telegram_notification":
                agent_name = args.get("agent_name") or "AI Agent"
                summary = args.get("summary") or "Tugas selesai."
                text = f"✅ [{agent_name}] Selesai Mengerjakan Tugas!\n📂 Workspace: {os.getcwd()}\n\n📝 Ringkasan:\n{summary}"
                ok = send_telegram_message(text)
                status_msg = "Notifikasi berhasil dikirim ke Telegram." if ok else "Gagal mengirim notifikasi (cek .env)."
                send_response(
                    req_id,
                    {"content": [{"type": "text", "text": status_msg}], "isError": not ok},
                )
            else:
                send_error(req_id, -32601, f"Tool tidak dikenal: {tool_name}")
        elif req_id is not None:
            send_response(req_id, {})


if __name__ == "__main__":
    main()
