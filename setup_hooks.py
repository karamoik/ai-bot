#!/usr/bin/env python3
"""
Installer Otomatis Notifikasi Telegram untuk SEMUA AI Agent di PC:
1. Google Antigravity (~/.gemini/config/hooks.json -> Stop Hook)
2. Claude Code (~/.claude/settings.json -> Stop Hook)
3. OpenCode (~/.config/opencode/plugin/telegram-notify.js -> session.idle Hook & opencode.json MCP)
4. Cursor (~/.cursor/mcp.json -> MCP Server)
5. Windsurf (~/.codeium/windsurf/mcp_config.json -> MCP Server)
"""

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
NOTIFY_SCRIPT = str(BASE_DIR / "notify.py")
MCP_SCRIPT = str(BASE_DIR / "mcp_server.py")


def load_json_safe(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def setup_antigravity(enable: bool = True) -> None:
    """Pasang Lifecycle Stop Hook di Google Antigravity."""
    hooks_file = Path.home() / ".gemini" / "config" / "hooks.json"
    data = load_json_safe(hooks_file)

    if enable:
        data["telegram-notifier"] = {
            "enabled": True,
            "Stop": [
                {
                    "type": "command",
                    "command": f'python "{NOTIFY_SCRIPT}" --hook --agent "Google Antigravity"',
                    "timeout": 15,
                }
            ],
        }
        save_json(hooks_file, data)
        print(f"✅ [Google Antigravity] Stop Hook aktif -> {hooks_file}")
    else:
        if "telegram-notifier" in data:
            data["telegram-notifier"]["enabled"] = False
            save_json(hooks_file, data)
        print(f"🛑 [Google Antigravity] Stop Hook dinonaktifkan.")


def setup_claude_code(enable: bool = True) -> None:
    """Pasang Lifecycle Stop Hook di Claude Code."""
    settings_file = Path.home() / ".claude" / "settings.json"
    data = load_json_safe(settings_file)

    if enable:
        hooks = data.setdefault("hooks", {})
        hooks["Stop"] = [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'python "{NOTIFY_SCRIPT}" --hook --agent "Claude Code"',
                    }
                ],
            }
        ]
        save_json(settings_file, data)
        print(f"✅ [Claude Code] Stop Hook aktif -> {settings_file}")
    else:
        if "hooks" in data and "Stop" in data["hooks"]:
            del data["hooks"]["Stop"]
            save_json(settings_file, data)
        print(f"🛑 [Claude Code] Stop Hook dinonaktifkan.")


def setup_opencode(enable: bool = True) -> None:
    """
    Untuk OpenCode v2, notifikasi sudah dipantau secara real-time oleh bot.py
    melalui database SQLite (~/.local/share/opencode/opencode.db), sehingga tidak
    memerlukan file plugin JS tambahan yang bisa memicu error versi schema.
    """
    opencode_dir = Path.home() / ".config" / "opencode"
    plugin_file = opencode_dir / "plugin" / "telegram-notify.js"
    if plugin_file.exists():
        plugin_file.unlink()
    if enable:
        print("✅ [OpenCode] Real-time SQLite Watcher aktif melalui bot.py (tanpa plugin JS)")
    else:
        print("🛑 [OpenCode] Auto-Notify dinonaktifkan.")


def setup_ide_mcp(ide_name: str, mcp_file: Path, enable: bool = True) -> None:
    """Pasang MCP Server Notifier untuk IDE (Cursor / Windsurf)."""
    data = load_json_safe(mcp_file)
    if enable:
        servers = data.setdefault("mcpServers", {})
        servers["telegram-notifier"] = {
            "command": "python",
            "args": [MCP_SCRIPT],
        }
        save_json(mcp_file, data)
        print(f"✅ [{ide_name}] MCP Notifier aktif -> {mcp_file}")
    else:
        if "mcpServers" in data and "telegram-notifier" in data["mcpServers"]:
            del data["mcpServers"]["telegram-notifier"]
            save_json(mcp_file, data)
        print(f"🛑 [{ide_name}] MCP Notifier dinonaktifkan.")


if __name__ == "__main__":
    enable_mode = "--disable" not in sys.argv
    print("=" * 65)
    print("🔔 MENGATUR NOTIFIKASI OTOMATIS UNTUK SEMUA AI AGENT...")
    print("=" * 65)
    setup_antigravity(enable=enable_mode)
    setup_claude_code(enable=enable_mode)
    setup_opencode(enable=enable_mode)
    setup_ide_mcp("Cursor", Path.home() / ".cursor" / "mcp.json", enable=enable_mode)
    setup_ide_mcp("Windsurf", Path.home() / ".codeium" / "windsurf" / "mcp_config.json", enable=enable_mode)
    print("=" * 65)
    if enable_mode:
        print("🎉 Semua AI Agent sudah terhubung ke sistem notifikasi Telegram!")
    else:
        print("🛑 Semua notifikasi otomatis telah dinonaktifkan.")
