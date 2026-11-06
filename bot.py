#!/usr/bin/env python3
"""
Universal AI Agent Telegram Bridge Bot — Rich Dashboard UI & Interactive File Explorer Edition.
Fitur UI Modern & Keamanan Berlapis:
1. Rich Telegram HTML UI: Mendukung <pre><code> (Kotak Terminal Gelap Monospace), <b>Badge</b>,
   dan <blockquote expandable> (Kartu Lipat Interaktif untuk Proses Berpikir AI).
2. Interactive GUI File Explorer (/files atau otomatis saat /cmd dir): Jelajahi folder, lihat foto,
   baca source code dengan syntax highlighting, & download file langsung dari layar HP!
3. Interactive Prompt Launchpad Card: Pilih Agent (dengan deteksi status instalasi otomatis),
   Model (mendukung model OpenCode & Antigravity), Project, atau Mode sebelum jalan.
4. Native Plan/Build Mode Enforcement: Mode AMAN otomatis mengaktifkan `--agent plan` (OpenCode)
   dan `--mode plan` (Antigravity) di level CLI.
5. Pembersih ANSI Escape Codes otomatis & eksekusi `.exe` langsung (`shell=False`) yang aman
   untuk prompt multi-baris.
"""

import ctypes
import glob
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
CONFIG_FILE = BASE_DIR / "config.json"
LOG_FILE = BASE_DIR / "activity.log"
PID_FILE = BASE_DIR / ".bot.pid"
UPLOADS_DIR = BASE_DIR / "uploads"
MAX_LOG_BYTES = 1 * 1024 * 1024
BOT_START_TIME = time.time()

SPINNERS = ["🧠💭", "⏳🔄", "⚡🧠", "🛠️🔃"]

ANSI_ESCAPE_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
OPENCODE_HEADER_RE = re.compile(r"(?m)^\s*>\s*(?:build|plan)\s*·\s*[^\n]+\n?")

DANGEROUS_PATTERNS = re.compile(
    r"\b(hapus|delete|remove|rm\s+-|del\s+/|rmdir|remove-item|format\s+|drop\s+table|drop\s+database|truncate\s+|reset\s+--hard|clean\s+-fd)\b",
    re.IGNORECASE,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
BINARY_EXTENSIONS = {
    ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz", ".exe", ".dll", ".so",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".db", ".sqlite", ".sqlite3",
    ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".ico", ".woff", ".woff2", ".ttf",
}


def strip_ansi(text: str) -> str:
    """Membersihkan kode warna/kontrol terminal ANSI (\x1b[...m) agar teks bersih di Telegram."""
    if not text:
        return ""
    cleaned = ANSI_ESCAPE_RE.sub("", text)
    return cleaned.replace("\r\n", "\n").replace("\r", "\n")


def clean_agent_stdout(text: str) -> str:
    """Membersihkan ANSI escape codes dan header internal `> build · model` dari stdout agent."""
    cleaned = strip_ansi(text)
    cleaned = OPENCODE_HEADER_RE.sub("", cleaned)
    return cleaned.strip()


def strip_html_tags(text: str) -> str:
    """Menghapus tag HTML jika diperlukan untuk fallback plain-text."""
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def e(text: str) -> str:
    """Escape teks biasa agar aman dirender di dalam Telegram HTML."""
    return html.escape(str(text or ""))


def md_to_tg_html(md_text: str) -> str:
    """
    Mengubah Markdown jawaban AI (blok kode ```...```, `inline`, **bold**, ### Heading)
    menjadi Telegram HTML yang rapi dan memiliki kotak kode gelap (<pre><code>).
    """
    if not md_text:
        return ""

    md_text = strip_ansi(md_text)
    # Pastikan jika teks terpotong di tengah blok kode ```, tutup otomatis agar HTML valid
    if md_text.count("```") % 2 == 1:
        md_text += "\n```"

    code_blocks = []

    def _save_code_block(match):
        lang = (match.group(1) or "").strip()
        code = e(match.group(2).strip("\n"))
        idx = len(code_blocks)
        if lang:
            code_blocks.append(f'<pre><code class="language-{e(lang)}">{code}</code></pre>')
        else:
            code_blocks.append(f"<pre><code>{code}</code></pre>")
        return f"@@CODEBLOCK_{idx}@@"

    # 1. Ekstrak fenced code blocks ```lang ... ```
    processed = re.sub(r"```([a-zA-Z0-9_-]*)\n?(.*?)```", _save_code_block, md_text, flags=re.DOTALL)

    # 2. Escape sisa HTML
    processed = e(processed)

    # 3. Inline code `...`
    processed = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", processed)

    # 4. Bold **...**
    processed = re.sub(r"\*\*([^\*\n]+)\*\*", r"<b>\1</b>", processed)

    # 5. Headings ### ...
    processed = re.sub(r"(?m)^#{1,4}\s+(.+)$", r"💠 <b>\1</b>", processed)

    # 6. Kembalikan fenced code blocks
    for idx, block_html in enumerate(code_blocks):
        processed = processed.replace(f"@@CODEBLOCK_{idx}@@", block_html)

    return processed


def resolve_cli_executable(bin_name: str) -> str:
    """
    Mencari path executable CLI di sistem.
    Khusus opencode di Windows (npm wrapper .cmd), otomatis mencari opencode.exe asli
    supaya dapat dijalankan langsung tanpa cmd.exe (shell=False) agar aman untuk prompt multi-baris.
    """
    found = shutil.which(bin_name)
    if not found:
        return ""
    found_path = Path(found)
    if os.name == "nt" and found_path.suffix.lower() in (".cmd", ".bat", ".ps1"):
        if bin_name.lower() == "opencode":
            direct_exe = found_path.parent / "node_modules" / "@opencode" / "cli" / "bin" / "opencode.exe"
            if direct_exe.exists():
                return str(direct_exe)
    return str(found_path)


def is_agent_installed(agent_key: str, cfg: dict) -> bool:
    """Mengecek apakah CLI untuk agent tertentu sudah terinstal di laptop."""
    agent_info = (cfg.get("agents") or {}).get(agent_key, {})
    cmd = agent_info.get("command") or []
    if not cmd:
        return False
    return bool(resolve_cli_executable(cmd[0]))


def make_progress_bar(elapsed_sec: int) -> str:
    """Membuat animasi bar visual untuk UI status sedang bekerja."""
    slots = 8
    filled = (elapsed_sec // 3) % (slots + 1)
    if filled == 0:
        filled = 1
    return "▰" * filled + "▱" * (slots - filled)


def start_windows_anti_sleep() -> None:
    if os.name != "nt":
        return

    def _keep_awake():
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        while True:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            except Exception:
                pass
            time.sleep(45)

    t = threading.Thread(target=_keep_awake, daemon=True)
    t.start()


def capture_laptop_screenshot(output_path: Path) -> bool:
    target_path = str(output_path).replace("'", "''")
    ps_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$csharp = @"
using System;
using System.Drawing;
using System.Threading;
using System.Runtime.InteropServices;

public class ScreenGrabber {{
    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr OpenDesktop(string lpszDesktop, uint dwFlags, bool fInherit, uint dwDesiredAccess);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetThreadDesktop(IntPtr hDesktop);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool CloseDesktop(IntPtr hDesktop);
    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int nIndex);
    [DllImport("user32.dll")]
    public static extern IntPtr GetDC(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);
    [DllImport("gdi32.dll")]
    public static extern IntPtr CreateCompatibleDC(IntPtr hdc);
    [DllImport("gdi32.dll")]
    public static extern IntPtr CreateCompatibleBitmap(IntPtr hdc, int nWidth, int nHeight);
    [DllImport("gdi32.dll")]
    public static extern IntPtr SelectObject(IntPtr hdc, IntPtr hgdiobj);
    [DllImport("gdi32.dll")]
    public static extern bool BitBlt(IntPtr hdcDest, int nXDest, int nYDest, int nWidth, int nHeight, IntPtr hdcSrc, int nXSrc, int nYSrc, int dwRop);
    [DllImport("gdi32.dll")]
    public static extern bool DeleteDC(IntPtr hdc);
    [DllImport("gdi32.dll")]
    public static extern bool DeleteObject(IntPtr hObject);

    public static bool Capture(string outPath) {{
        bool ok = false;
        Thread t = new Thread(() => {{
            try {{
                SetProcessDPIAware();
            }} catch {{}}

            IntPtr hDesk = OpenDesktop("Default", 0, false, 0x01FF);
            if (hDesk == IntPtr.Zero) {{
                hDesk = OpenDesktop("default", 0, false, 0x01FF);
            }}
            if (hDesk != IntPtr.Zero) {{
                SetThreadDesktop(hDesk);
            }}

            int w = GetSystemMetrics(0); // SM_CXSCREEN
            int h = GetSystemMetrics(1); // SM_CYSCREEN
            if (w <= 0 || h <= 0) return;

            IntPtr hdcScreen = GetDC(IntPtr.Zero);
            if (hdcScreen == IntPtr.Zero) return;
            IntPtr hdcMem = CreateCompatibleDC(hdcScreen);
            IntPtr hBmp = CreateCompatibleBitmap(hdcScreen, w, h);
            IntPtr hOld = SelectObject(hdcMem, hBmp);

            // 0x00CC0020 (SRCCOPY) | 0x40000000 (CAPTUREBLT)
            bool bltOk = BitBlt(hdcMem, 0, 0, w, h, hdcScreen, 0, 0, 0x40CC0020);
            if (bltOk) {{
                using (Bitmap bmp = Image.FromHbitmap(hBmp)) {{
                    bmp.Save(outPath, System.Drawing.Imaging.ImageFormat.Png);
                    ok = true;
                }}
            }}

            SelectObject(hdcMem, hOld);
            DeleteObject(hBmp);
            DeleteDC(hdcMem);
            ReleaseDC(IntPtr.Zero, hdcScreen);
            if (hDesk != IntPtr.Zero) {{
                CloseDesktop(hDesk);
            }}
        }});

        t.SetApartmentState(ApartmentState.STA);
        t.Start();
        t.Join(8000);
        return ok;
    }}
}}
"@
try {{
    Add-Type -TypeDefinition $csharp -ReferencedAssemblies System.Drawing
    $ok = [ScreenGrabber]::Capture('{target_path}')
    if (-not $ok -or -not (Test-Path '{target_path}')) {{
        exit 1
    }}
}} catch {{
    exit 1
}}
"""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
        return res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 20000
    except Exception:
        return False


def is_protected_folder(folder_path: str) -> tuple:
    norm = os.path.normcase(os.path.abspath(folder_path)).rstrip("\\/")
    user_home = os.path.normcase(str(Path.home())).rstrip("\\/")

    if len(norm) <= 3 and norm.endswith(":"):
        return True, f"Root Drive ({norm}\\) diblokir demi keamanan data."

    forbidden_exact = {
        user_home: "Folder utama User (C:\\Users\\willy) diblokir agar Desktop/Documents aman. Silakan pilih folder project koding Anda.",
        os.path.join(user_home, "desktop"): "Folder Desktop diblokir demi keamanan.",
        os.path.join(user_home, "documents"): "Folder Documents pribadi diblokir demi keamanan.",
        os.path.join(user_home, "downloads"): "Folder Downloads diblokir demi keamanan.",
    }
    if norm in forbidden_exact:
        return True, forbidden_exact[norm]

    for sys_prefix in ("c:\\windows", "c:\\program files", "c:\\program files (x86)", "c:\\programdata"):
        if norm == sys_prefix or norm.startswith(sys_prefix + "\\"):
            return True, f"Folder sistem Windows ({folder_path}) diblokir."

    return False, ""


def ensure_single_instance() -> None:
    my_pid = os.getpid()
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if old_pid != my_pid and old_pid > 0:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(old_pid)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    os.kill(old_pid, 9)
                time.sleep(1)
        except Exception:
            pass
    try:
        PID_FILE.write_text(str(my_pid), encoding="utf-8")
    except Exception:
        pass


def log_activity(text: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    clean_text = strip_ansi(text)
    line = f"[{ts}] {clean_text}"
    print(line, flush=True)
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            old_data = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
            LOG_FILE.write_text(old_data[-(MAX_LOG_BYTES // 2) :], encoding="utf-8")
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_env() -> dict:
    env_vars = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars


def save_env_key(key: str, value: str) -> None:
    lines = []
    found = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"⚠️ Gagal membaca config.json: {exc}")
    return {
        "default_agent": "opencode",
        "default_model": "opencode/deepseek-v4.1-flash-free",
        "default_workspace": "D:\\free_project",
        "safe_mode": True,
        "project_roots": ["D:\\free_project", "D:\\free_project\\laragon\\www"],
        "saved_projects": {"free_project": "D:\\free_project", "bot": str(BASE_DIR)},
        "agents": {
            "opencode": {
                "name": "OpenCode AI CLI",
                "command": ["opencode", "run", "--thinking", "--auto", "{prompt}"],
                "continue_flag": "-c",
                "file_flag": "-f",
                "model_flag": "-m",
                "readonly_flags": ["--agent", "plan"],
                "write_flags": ["--agent", "build"],
                "description": "Menjalankan OpenCode CLI dalam mode non-interaktif",
            },
            "agy": {
                "name": "Google Antigravity CLI",
                "command": ["agy", "-p", "{prompt}"],
                "continue_flag": "-c",
                "model_flag": "--model",
                "readonly_flags": ["--mode", "plan"],
                "write_flags": ["--mode", "accept-edits"],
                "description": "Menjalankan Google Antigravity Agent",
            },
        },
    }


def save_config(cfg: dict) -> None:
    if CONFIG_FILE.exists():
        try:
            disk_cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            merged_agents = disk_cfg.get("agents", {})
            merged_agents.update(cfg.get("agents", {}))
            cfg["agents"] = merged_agents
        except Exception:
            pass
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def discover_all_projects(cfg: dict) -> dict:
    projects = {}
    for k, v in cfg.get("saved_projects", {}).items():
        if os.path.isdir(v):
            projects[k] = os.path.abspath(v)

    roots = cfg.get("project_roots", ["D:\\free_project", "D:\\free_project\\laragon\\www"])
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            for entry in sorted(os.scandir(root), key=lambda x: x.name.lower()):
                if entry.is_dir() and not entry.name.startswith("."):
                    key = entry.name.lower()[:24]
                    projects[key] = os.path.abspath(entry.path)
        except Exception:
            pass
    return projects


def fetch_available_models(agent_key: str = "opencode") -> list:
    """
    Mengambil daftar model yang tersedia sesuai AI Agent aktif:
    - opencode: memanggil `opencode models`
    - agy: memanggil `agy models`
    """
    if agent_key == "agy":
        agy_default = [
            "gemini-4-argon-high",
            "gemini-4-argon-medium",
            "gemini-3.8-flash-high",
            "claude-opus-5-5-high",
            "claude-sonnet-5-5-high",
            "gpt-oss-120b-medium",
        ]
        agy_bin = resolve_cli_executable("agy")
        if agy_bin:
            try:
                res = subprocess.run(
                    [agy_bin, "models"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )
                if res.returncode == 0 and res.stdout.strip():
                    parsed = []
                    for line in strip_ansi(res.stdout).splitlines():
                        line = line.strip()
                        if not line or line.lower().startswith("fetching"):
                            continue
                        model_id = line.split()[0].strip()
                        if model_id:
                            parsed.append(model_id)
                    if parsed:
                        return parsed
            except Exception:
                pass
        return agy_default

    default_list = [
        "opencode/deepseek-v4.1-flash-free",
        "opencode/glm-5.3-flash-free",
        "opencode/mimo-v2.6-flash-free",
        "opencode/nemotron-3.5-lightning-free",
        "opencode/big-pickle",
        "opencode/nemotron-3.5-super-vl-free",
        "opencode/beam-free",
        "opencode/crouton-alpha-free",
        "opencode/flint-40b-free",
        "opencode/pulse-alpha-free",
    ]
    oc_bin = resolve_cli_executable("opencode")
    if oc_bin:
        try:
            use_shell = oc_bin.lower().endswith((".cmd", ".bat", ".ps1"))
            res = subprocess.run(
                [oc_bin, "models"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=use_shell,
                timeout=10,
            )
            if res.returncode == 0 and res.stdout.strip():
                models = [m.strip() for m in strip_ansi(res.stdout).splitlines() if m.strip() and "/" in m.strip()]
                if models:
                    oc_models = [m for m in models if m.startswith("opencode/")]
                    other_models = [m for m in models if not m.startswith("opencode/")]
                    return oc_models + other_models
        except Exception:
            pass
    return default_list


def is_model_compatible_with_agent(model_id: str, agent_key: str) -> bool:
    """Memastikan flag model yang dikirim cocok dengan CLI agent yang dipilih."""
    if not model_id:
        return False
    if agent_key == "opencode":
        return "/" in model_id
    if agent_key == "agy":
        return "/" not in model_id
    return True


def get_latest_opencode_thinking(since_ms: int = 0) -> tuple:
    """
    Mengambil data terstruktur (reasoning/thinking, tool aktif, dan jawaban teks bersih)
    langsung dari SQLite opencode.db untuk pesan yang di-update sejak `since_ms`.
    """
    opencode_db = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
    if not opencode_db.exists():
        return "", "", ""
    try:
        con = sqlite3.connect(str(opencode_db), timeout=2)
        cur = con.cursor()
        if since_ms > 0:
            row = cur.execute(
                "SELECT data FROM session_message WHERE type='assistant' AND time_updated >= ? ORDER BY time_updated DESC LIMIT 1",
                (since_ms,),
            ).fetchone()
        else:
            row = cur.execute(
                "SELECT data FROM session_message WHERE type='assistant' ORDER BY time_updated DESC LIMIT 1"
            ).fetchone()
        con.close()
        if not row or not row[0]:
            return "", "", ""
        data = json.loads(row[0])
        parts = data.get("content") or []
        thinking_list = []
        tool_list = []
        text_list = []
        for p in parts:
            ptype = p.get("type", "")
            if ptype == "reasoning" and p.get("text"):
                thinking_list.append(p["text"].strip())
            elif "tool" in ptype:
                tname = p.get("name") or p.get("tool") or p.get("toolName") or ptype
                tool_list.append(str(tname))
            elif ptype == "text" and p.get("text"):
                text_list.append(p["text"].strip())
        thinking_str = "\n\n".join(thinking_list).strip()
        tool_str = ", ".join(tool_list[-3:]).strip()
        ans_str = "\n\n".join(text_list).strip()
        return thinking_str, tool_str, ans_str
    except Exception:
        return "", "", ""


def get_git_changes_summary_html(workspace: str) -> str:
    if not os.path.isdir(workspace):
        return ""
    try:
        res = subprocess.run(
            ["git", "status", "--short"],
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return ""
        status_lines = res.stdout.strip().splitlines()
        preview = "\n".join(e(line) for line in status_lines[:10])
        if len(status_lines) > 10:
            preview += f"\n... (+{len(status_lines) - 10} file lainnya)"
        return f"\n\n📁 <b>File Berubah di Git ({len(status_lines)} file):</b>\n<pre><code>{preview}</code></pre>"
    except Exception:
        return ""


def make_bar(percent: int) -> str:
    filled = max(0, min(10, round(percent / 10)))
    return "█" * filled + "░" * (10 - filled)


def get_system_health_html() -> str:
    uptime_sec = int(time.time() - BOT_START_TIME)
    hours, rem = divmod(uptime_sec, 3600)
    mins, secs = divmod(rem, 60)
    uptime_str = f"{hours}j {mins}m {secs}d"

    rows = [
        "╭─── 💻 <b>DASHBOARD KESEHATAN LAPTOP</b> ───╮",
        f"│ ⏱️ <b>Uptime Bot :</b> <code>{uptime_str}</code>",
        "│ ☕ <b>Wake-Lock  :</b> <code>Aktif (Anti-Sleep)</code>",
    ]

    if os.name == "nt":
        ps_cmd = (
            "$bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; "
            "$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average; "
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "Write-Output \"BAT:$($bat.EstimatedChargeRemaining)|$($bat.BatteryStatus)\"; "
            "Write-Output \"CPU:$cpu\"; "
            "Write-Output \"RAM:$($os.FreePhysicalMemory)|$($os.TotalVisibleMemorySize)\""
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=8,
            )
            for row in res.stdout.splitlines():
                if row.startswith("BAT:"):
                    parts = row[4:].split("|")
                    pct_s = parts[0].strip()
                    st = parts[1].strip() if len(parts) > 1 else ""
                    if pct_s.isdigit():
                        pct = int(pct_s)
                        charging = "⚡ AC Charging" if st in ("2", "6", "7", "8", "9") else "🔋 Battery"
                        rows.append(f"│ 🔋 <b>Baterai    :</b> <code>[{make_bar(pct)}] {pct}%</code> ({charging})")
                    else:
                        rows.append("│ 🔌 <b>Daya       :</b> <code>Listrik AC Langsung</code>")
                elif row.startswith("CPU:"):
                    cpu_s = row[4:].strip() or "0"
                    cpu_val = int(float(cpu_s)) if cpu_s.replace(".", "").isdigit() else 0
                    rows.append(f"│ 🧠 <b>Beban CPU  :</b> <code>[{make_bar(cpu_val)}] {cpu_val}%</code>")
                elif row.startswith("RAM:"):
                    parts = row[4:].split("|")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        free_gb = round(int(parts[0]) / (1024 * 1024), 1)
                        total_gb = round(int(parts[1]) / (1024 * 1024), 1)
                        used_gb = round(total_gb - free_gb, 1)
                        pct_ram = round((used_gb / total_gb) * 100) if total_gb else 0
                        rows.append(f"│ 💾 <b>RAM Pakai  :</b> <code>[{make_bar(pct_ram)}] {pct_ram}%</code> ({used_gb}/{total_gb} GB)")
        except Exception:
            pass

    for drive in ("C:\\", "D:\\"):
        if os.path.exists(drive):
            try:
                usage = shutil.disk_usage(drive)
                free_gb = round(usage.free / (1024**3), 1)
                used_pct = round(((usage.total - usage.free) / usage.total) * 100) if usage.total else 0
                rows.append(f"│ 💿 <b>Disk {drive[:2]}    :</b> <code>[{make_bar(used_pct)}] Sisa {free_gb} GB</code>")
            except Exception:
                pass

    rows.append("╰────────────────────────────────────╯")
    return "\n".join(rows)


class TelegramBridgeBot:
    def __init__(self, token: str, allowed_chat_id: str = ""):
        self.token = token
        self.allowed_chat_id = str(allowed_chat_id).strip()
        self.api_base = f"https://api.telegram.org/bot{self.token}"
        self.file_base = f"https://api.telegram.org/file/bot{self.token}"
        self.config = load_config()
        self.active_agent = self.config.get("default_agent", "opencode")
        if not is_agent_installed(self.active_agent, self.config):
            self.active_agent = "opencode"
            self.config["default_agent"] = "opencode"
            save_config(self.config)

        self.active_model = self.config.get("default_model", "opencode/big-pickle")
        self.safe_mode = bool(self.config.get("safe_mode", True))
        self.continue_session = True
        self.active_workspace = self.config.get("default_workspace", "D:\\free_project")

        blocked, _ = is_protected_folder(self.active_workspace)
        if not os.path.isdir(self.active_workspace) or blocked:
            self.active_workspace = str(BASE_DIR)

        self.cached_models = fetch_available_models(self.active_agent)
        self.explorer_entries = []
        self.tasks_lock = threading.Lock()
        self.task_counter = 0
        self.running_tasks = {}
        self.pending_confirmations = {}
        self.pending_launchpads = {}

    def api_call(self, method: str, payload: dict, timeout: int = 35) -> dict:
        url = f"{self.api_base}/{method}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            return {"ok": False, "error": err_body}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def download_telegram_file(self, file_id: str, dest_name: str) -> str:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            existing = sorted(UPLOADS_DIR.glob("*"), key=lambda p: p.stat().st_mtime)
            for old_f in existing[:-15]:
                old_f.unlink(missing_ok=True)
        except Exception:
            pass

        info = self.api_call("getFile", {"file_id": file_id}, timeout=15)
        if not info.get("ok") or not info.get("result"):
            return ""
        remote_path = info["result"].get("file_path", "")
        if not remote_path:
            return ""
        ext = os.path.splitext(remote_path)[1] or ".jpg"
        if not os.path.splitext(dest_name)[1]:
            dest_name += ext
        local_path = UPLOADS_DIR / dest_name
        url = f"{self.file_base}/{remote_path}"
        try:
            with urllib.request.urlopen(url, timeout=25) as resp:
                local_path.write_bytes(resp.read())
            return str(local_path)
        except Exception:
            return ""

    def send_chat_action(self, chat_id: str, action: str = "typing") -> None:
        if not chat_id:
            return
        self.api_call("sendChatAction", {"chat_id": chat_id, "action": action}, timeout=5)

    def send_message(self, chat_id: str, text: str, reply_markup: dict = None, parse_mode: str = "HTML") -> int:
        if not chat_id:
            return 0
        if not text:
            text = "(Output kosong)"
        chunk_size = 3800
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
        last_msg_id = 0
        for idx, chunk in enumerate(chunks):
            prefix = f"<b>[Bagian {idx + 1}/{len(chunks)}]</b>\n" if len(chunks) > 1 else ""
            payload = {"chat_id": chat_id, "text": prefix + chunk}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if idx == len(chunks) - 1 and reply_markup:
                payload["reply_markup"] = reply_markup
            res = self.api_call("sendMessage", payload, timeout=15)
            # Fallback ke plain text bersih (tanpa tag HTML bocor) jika ada tag HTML terpotong
            if not res.get("ok") and parse_mode:
                payload.pop("parse_mode", None)
                payload["text"] = strip_html_tags(prefix + chunk)
                res = self.api_call("sendMessage", payload, timeout=15)
            if res.get("ok") and res.get("result"):
                last_msg_id = res["result"].get("message_id", 0)
        return last_msg_id

    def edit_message(self, chat_id: str, message_id: int, text: str, reply_markup: dict = None, parse_mode: str = "HTML") -> bool:
        if not chat_id or not message_id:
            return False
        if len(text) > 3950:
            text = text[:3900] + "\n..."
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        res = self.api_call("editMessageText", payload, timeout=10)
        if not res.get("ok") and parse_mode:
            err_str = str(res.get("error", ""))
            if "message is not modified" in err_str:
                return True
            payload.pop("parse_mode", None)
            payload["text"] = strip_html_tags(text)
            res = self.api_call("editMessageText", payload, timeout=10)
        return bool(res.get("ok"))

    def delete_message(self, chat_id: str, message_id: int) -> None:
        if not chat_id or not message_id:
            return
        self.api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id}, timeout=10)

    def send_binary_file(self, chat_id: str, field_name: str, method: str, file_path: Path, caption: str = "") -> bool:
        if not chat_id or not file_path.exists():
            return False
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        lines = []

        def add_field(name: str, val: str):
            lines.append(f"--{boundary}".encode("utf-8"))
            lines.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
            lines.append(b"")
            lines.append(str(val).encode("utf-8"))

        add_field("chat_id", chat_id)
        if caption:
            add_field("caption", caption[:1000])

        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"'.encode("utf-8"))
        lines.append(b"Content-Type: application/octet-stream")
        lines.append(b"")
        lines.append(file_path.read_bytes())
        lines.append(f"--{boundary}--".encode("utf-8"))
        lines.append(b"")

        body = b"\r\n".join(lines)
        url = f"{self.api_base}/{method}"
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status == 200
        except Exception:
            return False

    def send_document_content(self, chat_id: str, filename: str, content_str: str, caption: str = "") -> bool:
        tmp_path = BASE_DIR / filename
        try:
            tmp_path.write_text(content_str, encoding="utf-8", errors="replace")
            return self.send_binary_file(chat_id, "document", "sendDocument", tmp_path, caption)
        finally:
            tmp_path.unlink(missing_ok=True)

    def mode_label(self) -> str:
        return "🟢 AMAN (Plan / Read-Only)" if self.safe_mode else "🔴 EDIT (Build / Write Aktif)"

    def default_action_buttons(self) -> dict:
        if self.safe_mode:
            toggle_txt = "🟢 Mode: AMAN (Plan/Read-Only) | Tap -> 🔴 Edit"
        else:
            toggle_txt = "🔴 Mode: EDIT (Write Aktif) | Tap -> 🟢 Aman"
        short_model = self.active_model.split("/")[-1] if self.active_model else "auto"
        return {
            "inline_keyboard": [
                [
                    {"text": toggle_txt, "callback_data": "cb:toggle_mode"},
                ],
                [
                    {"text": "🗂️ File Explorer (GUI)", "callback_data": "cb:files:0"},
                    {"text": "📂 Pindah Project", "callback_data": "cb:menu_projects"},
                ],
                [
                    {"text": f"🧠 Model: {short_model[:18]}", "callback_data": "cb:menu_models:0"},
                    {"text": f"🤖 Agent: {self.active_agent.upper()}", "callback_data": "cb:menu_agents"},
                ],
                [
                    {"text": "📄 Git Diff", "callback_data": "cb:diff"},
                    {"text": "📊 Git Status", "callback_data": "cb:status"},
                    {"text": "🧹 Sesi Baru", "callback_data": "cb:new_session"},
                ],
                [
                    {"text": "⏪ Undo AI", "callback_data": "cb:ask_undo"},
                    {"text": "📸 Layar", "callback_data": "cb:screenshot"},
                    {"text": "💻 /sys", "callback_data": "cb:sys"},
                ],
            ]
        }

    def build_file_explorer_ui(self, page: int = 0) -> tuple:
        """
        Membangun UI File Explorer Interaktif (seperti VS Code Explorer / File Manager)
        untuk melihat isi folder aktif, klik subfolder untuk masuk, atau klik file untuk baca/download!
        """
        cwd = Path(self.active_workspace)
        dirs = []
        files = []
        try:
            for item in sorted(cwd.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name.startswith(".") and item.name not in (".env", ".gitignore"):
                    continue
                if item.is_dir():
                    dirs.append(item)
                else:
                    files.append(item)
        except Exception as exc:
            return f"⚠️ Gagal membaca direktori: <code>{e(exc)}</code>", self.default_action_buttons()

        all_items = dirs + files
        self.explorer_entries = [str(x) for x in all_items]

        page_size = 10
        total = len(all_items)
        max_page = max(0, (total - 1) // page_size)
        page = max(0, min(page, max_page))
        start_i = page * page_size
        slice_items = all_items[start_i : start_i + page_size]

        table_lines = []
        for it in slice_items:
            if it.is_dir():
                table_lines.append(f"📁 {it.name}/")
            else:
                try:
                    sz = it.stat().st_size
                    sz_str = (
                        f"{sz} B"
                        if sz < 1024
                        else (f"{round(sz / 1024, 1)} KB" if sz < 1048576 else f"{round(sz / 1048576, 1)} MB")
                    )
                except Exception:
                    sz_str = ""
                icon = "🖼️" if it.suffix.lower() in IMAGE_EXTENSIONS else "📄"
                table_lines.append(f"{icon} {it.name:<26} {sz_str:>8}")

        listing_str = "\n".join(table_lines) if table_lines else "(Folder kosong)"

        text = (
            "╭─── 🗂️ <b>INTERACTIVE FILE EXPLORER</b> ───╮\n"
            f"│ 📍 <b>Lokasi:</b> <code>{e(str(cwd))}</code>\n"
            f"│ 📊 <b>Total :</b> <code>{len(dirs)} Folder, {len(files)} File</code> (Hal {page + 1}/{max_page + 1})\n"
            "╰────────────────────────────────────╯\n"
            f"<pre><code>{e(listing_str)}</code></pre>\n"
            "👇 <i>Tap Folder (📁) untuk masuk, atau File (📄/🖼️) untuk melihat/mengunduh isinya:</i>"
        )

        kb_rows = []
        row = []
        for idx, it in enumerate(slice_items):
            real_idx = start_i + idx
            if it.is_dir():
                icon = "📁"
            elif it.suffix.lower() in IMAGE_EXTENSIONS:
                icon = "🖼️"
            else:
                icon = "📄"
            short_n = it.name[:18] + (".." if len(it.name) > 18 else "")
            row.append({"text": f"{icon} {short_n}", "callback_data": f"fexp_open:{real_idx}"})
            if len(row) == 2:
                kb_rows.append(row)
                row = []
        if row:
            kb_rows.append(row)

        nav_row = []
        if page > 0:
            nav_row.append({"text": "⬅️ Prev", "callback_data": f"cb:files:{page - 1}"})
        parent_dir = str(cwd.parent)
        blocked_parent, _ = is_protected_folder(parent_dir)
        if cwd.parent != cwd and not blocked_parent:
            nav_row.append({"text": "⬆️ Naik 1 Folder (..)", "callback_data": "fexp_up"})
        if page < max_page:
            nav_row.append({"text": "Next ➡️", "callback_data": f"cb:files:{page + 1}"})
        if nav_row:
            kb_rows.append(nav_row)

        kb_rows.append(
            [
                {"text": "🔄 Refresh", "callback_data": f"cb:files:{page}"},
                {"text": "📂 Daftar Project", "callback_data": "cb:menu_projects"},
                {"text": "🏠 Menu Utama", "callback_data": "cb:home"},
            ]
        )
        return text, {"inline_keyboard": kb_rows}

    def build_launchpad_text_and_kb(self, pad_id: str) -> tuple:
        pad = self.pending_launchpads.get(pad_id, {})
        prompt = pad.get("prompt", "")
        attached = pad.get("attached_file", "")
        attach_line = f"\n│ 📎 <b>Lampiran :</b> <code>{e(os.path.basename(attached))}</code>" if attached else ""
        mode_btn = "🟢 Mode: AMAN (Tap -> 🔴 Edit)" if self.safe_mode else "🔴 Mode: EDIT (Tap -> 🟢 Aman)"
        short_model = self.active_model or "Default"

        text = (
            "╭─── 🎯 <b>KONFIRMASI EKSEKUSI PROMPT</b> ───╮\n"
            f"│ 📂 <b>Project :</b> <code>{e(self.active_workspace)}</code>\n"
            f"│ 🛡️ <b>Mode    :</b> <code>{e(self.mode_label())}</code>\n"
            f"│ 🧠 <b>Model   :</b> <code>{e(short_model)}</code>{attach_line}\n"
            "╰─────────────────────────────────────╯\n\n"
            f"💬 <b>Prompt Anda:</b>\n<pre><code>{e(prompt[:600])}</code></pre>\n"
            "👇 <b>Pilih AI Agent untuk mulai mengeksekusi:</b>\n"
            "<i>(⭐/🟢 = Siap di Laptop | ⚪ = CLI Belum Terinstal)</i>"
        )

        self.config = load_config()
        agents = self.config.get("agents", {})
        # Urutkan agar agent yang sudah terinstal tampil paling atas
        sorted_keys = sorted(agents.keys(), key=lambda k: (not is_agent_installed(k, self.config), k != self.active_agent))
        agent_buttons = []
        row = []
        for k in sorted_keys:
            installed = is_agent_installed(k, self.config)
            if k == self.active_agent and installed:
                badge = "⭐ "
            elif installed:
                badge = "🟢 "
            else:
                badge = "⚪ "
            row.append({"text": f"{badge}{k.upper()}", "callback_data": f"pad_run:{pad_id}:{k}"})
            if len(row) == 2:
                agent_buttons.append(row)
                row = []
        if row:
            agent_buttons.append(row)

        kb_rows = list(agent_buttons)
        kb_rows.append(
            [
                {"text": f"🧠 Model ({short_model.split('/')[-1][:14]})", "callback_data": f"pad_models:{pad_id}:0"},
                {"text": "📂 Ganti Project", "callback_data": f"pad_projects:{pad_id}"},
            ]
        )
        kb_rows.append(
            [
                {"text": mode_btn, "callback_data": f"pad_mode:{pad_id}"},
                {"text": "❌ Batalkan", "callback_data": f"pad_cancel:{pad_id}"},
            ]
        )
        return text, {"inline_keyboard": kb_rows}

    def build_models_keyboard(self, page: int = 0, pad_id: str = "") -> dict:
        if not self.cached_models:
            self.cached_models = fetch_available_models(self.active_agent)

        page_size = 8
        total = len(self.cached_models)
        max_page = max(0, (total - 1) // page_size)
        page = max(0, min(page, max_page))
        start_idx = page * page_size
        slice_models = self.cached_models[start_idx : start_idx + page_size]

        rows = []
        for idx, m in enumerate(slice_models):
            real_idx = start_idx + idx
            icon = "✅" if m == self.active_model else "🧠"
            cb_data = f"pad_setm:{pad_id}:{real_idx}" if pad_id else f"set_model:{real_idx}"
            rows.append([{"text": f"{icon} {m}", "callback_data": cb_data}])

        nav_row = []
        if page > 0:
            prev_cb = f"pad_models:{pad_id}:{page - 1}" if pad_id else f"cb:menu_models:{page - 1}"
            nav_row.append({"text": "⬅️ Prev", "callback_data": prev_cb})
        if page < max_page:
            next_cb = f"pad_models:{pad_id}:{page + 1}" if pad_id else f"cb:menu_models:{page + 1}"
            nav_row.append({"text": f"Next ({page + 2}/{max_page + 1}) ➡️", "callback_data": next_cb})
        if nav_row:
            rows.append(nav_row)

        extra_row = [{"text": "🔄 Refresh Model", "callback_data": f"pad_refm:{pad_id}" if pad_id else "cb:refresh_models"}]
        if pad_id:
            extra_row.append({"text": "🔙 Kembali ke Prompt", "callback_data": f"pad_back:{pad_id}"})
        else:
            extra_row.append({"text": "🏠 Menu Utama", "callback_data": "cb:home"})
        rows.append(extra_row)
        return {"inline_keyboard": rows}

    def build_agents_keyboard(self) -> dict:
        self.config = load_config()
        rows = []
        current_row = []
        agents = self.config.get("agents", {})
        sorted_keys = sorted(agents.keys(), key=lambda k: (not is_agent_installed(k, self.config), k != self.active_agent))
        for k in sorted_keys:
            installed = is_agent_installed(k, self.config)
            if k == self.active_agent and installed:
                icon = "✅"
            elif installed:
                icon = "🟢"
            else:
                icon = "⚪"
            current_row.append({"text": f"{icon} {k.upper()}", "callback_data": f"set_agent:{k}"})
            if len(current_row) == 2:
                rows.append(current_row)
                current_row = []
        if current_row:
            rows.append(current_row)
        rows.append([{"text": "🏠 Menu Utama", "callback_data": "cb:home"}])
        return {"inline_keyboard": rows}

    def build_projects_keyboard(self, pad_id: str = "") -> dict:
        self.config = load_config()
        all_projs = discover_all_projects(self.config)
        rows = []
        for k, v in all_projs.items():
            is_curr = os.path.normcase(os.path.abspath(v)) == os.path.normcase(os.path.abspath(self.active_workspace))
            icon = "✅" if is_curr else "📂"
            cb = f"pad_setp:{pad_id}:{k}" if pad_id else f"set_proj:{k}"
            rows.append([{"text": f"{icon} {k} ({v})", "callback_data": cb}])
        if pad_id:
            rows.append([{"text": "🔙 Kembali ke Prompt", "callback_data": f"pad_back:{pad_id}"}])
        else:
            rows.append(
                [
                    {"text": "🗂️ Buka File Explorer", "callback_data": "cb:files:0"},
                    {"text": "🏠 Menu Utama", "callback_data": "cb:home"},
                ]
            )
        return {"inline_keyboard": rows}

    def start_session_watcher(self) -> None:
        t = threading.Thread(target=self._watcher_loop, daemon=True)
        t.start()

    def _watcher_loop(self) -> None:
        agy_seen = {}
        for p in glob.glob(str(Path.home() / ".gemini" / "*" / "brain" / "*" / ".system_generated" / "logs" / "transcript.jsonl")):
            try:
                agy_seen[p] = os.path.getmtime(p)
            except Exception:
                pass

        opencode_db = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
        last_opencode_ts = int(time.time() * 1000)
        if opencode_db.exists():
            try:
                con = sqlite3.connect(str(opencode_db))
                row = con.execute("SELECT MAX(time_updated) FROM session_message").fetchone()
                if row and row[0]:
                    last_opencode_ts = int(row[0])
                con.close()
            except Exception:
                pass

        notified_keys = set()
        active_pc_sessions = {}

        while True:
            time.sleep(2.5)
            if not self.allowed_chat_id:
                continue

            now = time.time()

            # 1. Pantau Google Antigravity transcripts
            try:
                pattern = str(Path.home() / ".gemini" / "*" / "brain" / "*" / ".system_generated" / "logs" / "transcript.jsonl")
                for p in glob.glob(pattern):
                    try:
                        mtime = os.path.getmtime(p)
                    except Exception:
                        continue
                    prev_mtime = agy_seen.get(p, 0)
                    sess_key = f"agy_live:{p}"

                    if mtime > prev_mtime:
                        lines = Path(p).read_text(encoding="utf-8", errors="ignore").splitlines()
                        if not lines:
                            continue
                        last_obj = json.loads(lines[-1])
                        step_idx = last_obj.get("step_index")
                        step_type = last_obj.get("type")
                        status = last_obj.get("status")
                        has_tools = bool(last_obj.get("tool_calls"))
                        content = (last_obj.get("content") or "").strip()
                        thinking = (last_obj.get("thinking") or "").strip()

                        last_user_prompt = ""
                        for rev_line in reversed(lines):
                            try:
                                obj = json.loads(rev_line)
                                if obj.get("type") == "USER_INPUT" and obj.get("content"):
                                    raw_u = obj.get("content", "")
                                    if "<USER_REQUEST>" in raw_u and "</USER_REQUEST>" in raw_u:
                                        raw_u = raw_u.split("<USER_REQUEST>", 1)[1].split("</USER_REQUEST>", 1)[0].strip()
                                    last_user_prompt = raw_u.strip()
                                    break
                            except Exception:
                                pass

                        is_finished = (step_type == "PLANNER_RESPONSE" and status == "DONE" and not has_tools and bool(content))

                        if not is_finished:
                            agy_seen[p] = mtime
                            self.send_chat_action(self.allowed_chat_id, "typing")
                            current_action = "🧠 AI sedang berpikir & menganalisis..."
                            if step_type == "PLANNER_RESPONSE" and has_tools:
                                tcalls = last_obj.get("tool_calls") or []
                                if tcalls:
                                    tname = tcalls[0].get("name", "tool")
                                    current_action = f"🔧 Menjalankan tool: <code>{e(tname)}</code>"
                            elif step_type != "USER_INPUT":
                                current_action = f"⚙️ Memproses hasil (<code>{e(step_type.lower())}</code>)..."

                            think_snippet = f"\n<blockquote expandable>💭 <b>Proses Berpikir:</b>\n{e(thinking[-350:])}</blockquote>" if thinking else ""

                            if sess_key not in active_pc_sessions:
                                msg_txt = (
                                    "╭─── 🧠💭 <b>ANTIGRAVITY SEDANG BEKERJA</b> ───╮\n"
                                    f"│ ⏱️ <b>Waktu  :</b> <code>0s [{make_progress_bar(0)}]</code>\n"
                                    f"│ 💬 <b>Prompt :</b> <code>{e(last_user_prompt[:120])}</code>\n"
                                    "╰─────────────────────────────────────╯\n"
                                    f"{current_action}{think_snippet}"
                                )
                                mid = self.send_message(self.allowed_chat_id, msg_txt)
                                active_pc_sessions[sess_key] = {
                                    "msg_id": mid,
                                    "start_ts": now,
                                    "prompt": last_user_prompt,
                                    "action": current_action,
                                    "thinking": thinking[-350:] if thinking else "",
                                    "tick": 0,
                                    "last_activity": now,
                                }
                            else:
                                info = active_pc_sessions[sess_key]
                                info["action"] = current_action
                                if thinking:
                                    info["thinking"] = thinking[-350:]
                                info["last_activity"] = now
                        else:
                            if now - mtime < 1.5:
                                continue
                            agy_seen[p] = mtime

                            if sess_key in active_pc_sessions:
                                old_info = active_pc_sessions.pop(sess_key)
                                self.delete_message(self.allowed_chat_id, old_info.get("msg_id", 0))

                            dedup_key = f"agy:{p}:{step_idx}"
                            if dedup_key in notified_keys:
                                continue
                            notified_keys.add(dedup_key)

                            summary = content[:1200] + ("..." if len(content) > 1200 else "")
                            git_info = get_git_changes_summary_html(self.active_workspace)
                            msg = (
                                "╭─── ✅ <b>ANTIGRAVITY SELESAI BEKERJA</b> ───╮\n"
                                f"│ 📂 <b>Folder :</b> <code>{e(self.active_workspace)}</code>\n"
                                f"│ 💬 <b>Prompt :</b> <code>{e(last_user_prompt[:150])}</code>\n"
                                "╰────────────────────────────────────╯\n\n"
                                f"{md_to_tg_html(summary)}{git_info}"
                            )
                            self.send_message(self.allowed_chat_id, msg, reply_markup=self.default_action_buttons())

                    if sess_key in active_pc_sessions:
                        info = active_pc_sessions[sess_key]
                        elapsed = int(now - info["start_ts"])
                        if now - info["last_activity"] > 600:
                            active_pc_sessions.pop(sess_key, None)
                        else:
                            info["tick"] += 1
                            spin = SPINNERS[info["tick"] % len(SPINNERS)]
                            self.send_chat_action(self.allowed_chat_id, "typing")
                            think_blk = f"\n<blockquote expandable>💭 <b>Proses Berpikir:</b>\n{e(info['thinking'])}</blockquote>" if info.get("thinking") else ""
                            msg_txt = (
                                f"╭─── {spin} <b>ANTIGRAVITY SEDANG BEKERJA</b> ───╮\n"
                                f"│ ⏱️ <b>Waktu  :</b> <code>{elapsed}s [{make_progress_bar(elapsed)}]</code>\n"
                                f"│ 💬 <b>Prompt :</b> <code>{e(info['prompt'][:120])}</code>\n"
                                "╰─────────────────────────────────────╯\n"
                                f"{info['action']}{think_blk}"
                            )
                            self.edit_message(self.allowed_chat_id, info["msg_id"], msg_txt)
            except Exception:
                pass

            # 2. Pantau OpenCode SQLite DB (session_message)
            if opencode_db.exists():
                try:
                    con = sqlite3.connect(str(opencode_db))
                    cur = con.cursor()
                    rows = cur.execute(
                        "SELECT id, session_id, type, time_updated, data FROM session_message WHERE time_updated > ? ORDER BY time_updated ASC",
                        (last_opencode_ts,),
                    ).fetchall()
                    for row_id, sess_id, msg_type, t_upd, raw_data in rows:
                        last_opencode_ts = max(last_opencode_ts, int(t_upd))
                        oc_live_key = f"oc_live:{sess_id}"

                        if msg_type == "user":
                            with self.tasks_lock:
                                hp_running_oc = any(t["agent"] == "opencode" for t in self.running_tasks.values())
                            if not hp_running_oc:
                                u_txt = ""
                                try:
                                    u_txt = json.loads(raw_data).get("text", "")
                                except Exception:
                                    pass
                                self.send_chat_action(self.allowed_chat_id, "typing")
                                if oc_live_key not in active_pc_sessions:
                                    mid = self.send_message(
                                        self.allowed_chat_id,
                                        "╭─── 🧠💭 <b>OPENCODE SEDANG BERPIKIR</b> ───╮\n"
                                        f"│ ⏱️ <b>Waktu  :</b> <code>0s [{make_progress_bar(0)}]</code>\n"
                                        f"│ 💬 <b>Prompt :</b> <code>{e(u_txt[:140])}</code>\n"
                                        "╰────────────────────────────────────╯",
                                    )
                                    active_pc_sessions[oc_live_key] = {
                                        "msg_id": mid,
                                        "start_ts": now,
                                        "start_ms": int(now * 1000) - 2000,
                                        "prompt": u_txt,
                                        "tick": 0,
                                        "last_activity": now,
                                    }

                        elif msg_type == "idle":
                            if oc_live_key in active_pc_sessions:
                                old_info = active_pc_sessions.pop(oc_live_key)
                                self.delete_message(self.allowed_chat_id, old_info.get("msg_id", 0))

                            dedup_key = f"oc:{row_id}"
                            if dedup_key in notified_keys:
                                continue
                            notified_keys.add(dedup_key)

                            with self.tasks_lock:
                                hp_running_oc = any(t["agent"] == "opencode" for t in self.running_tasks.values())
                            if hp_running_oc:
                                continue

                            asst_row = cur.execute(
                                "SELECT data FROM session_message WHERE session_id=? AND type='assistant' ORDER BY time_updated DESC LIMIT 1",
                                (sess_id,),
                            ).fetchone()
                            user_row = cur.execute(
                                "SELECT data FROM session_message WHERE session_id=? AND type='user' ORDER BY time_updated DESC LIMIT 1",
                                (sess_id,),
                            ).fetchone()

                            user_txt = ""
                            if user_row and user_row[0]:
                                user_txt = json.loads(user_row[0]).get("text", "")

                            asst_txt = ""
                            think_txt = ""
                            model_id = ""
                            if asst_row and asst_row[0]:
                                a_data = json.loads(asst_row[0])
                                model_id = (a_data.get("model") or {}).get("id", "")
                                parts = a_data.get("content") or []
                                asst_txt = "\n\n".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
                                think_txt = "\n\n".join(p.get("text", "") for p in parts if p.get("type") == "reasoning").strip()

                            if asst_txt:
                                summary = asst_txt[:1200] + ("..." if len(asst_txt) > 1200 else "")
                                think_card = (
                                    f"<blockquote expandable>💭 <b>Proses Berpikir AI:</b>\n{e(think_txt[:500])}</blockquote>\n\n"
                                    if think_txt
                                    else ""
                                )
                                git_info = get_git_changes_summary_html(self.active_workspace)
                                msg = (
                                    "╭─── ✅ <b>OPENCODE SELESAI BEKERJA</b> ───╮\n"
                                    f"│ 🧠 <b>Model  :</b> <code>{e(model_id)}</code>\n"
                                    f"│ 💬 <b>Prompt :</b> <code>{e(user_txt[:150])}</code>\n"
                                    "╰───────────────────────────────────╯\n\n"
                                    f"{think_card}{md_to_tg_html(summary)}{git_info}"
                                )
                                self.send_message(self.allowed_chat_id, msg, reply_markup=self.default_action_buttons())

                    for k in list(active_pc_sessions.keys()):
                        if k.startswith("oc_live:"):
                            info = active_pc_sessions[k]
                            elapsed = int(now - info["start_ts"])
                            if now - info["last_activity"] > 300:
                                active_pc_sessions.pop(k, None)
                            else:
                                info["tick"] += 1
                                spin = SPINNERS[info["tick"] % len(SPINNERS)]
                                self.send_chat_action(self.allowed_chat_id, "typing")
                                think_txt, tool_txt, _ = get_latest_opencode_thinking(since_ms=info.get("start_ms", 0))
                                extra_live = ""
                                if tool_txt:
                                    extra_live += f"\n🔧 <b>Tool Aktif:</b> <code>{e(tool_txt)}</code>"
                                if think_txt:
                                    extra_live += f"\n<blockquote expandable>💭 <b>Sedang Berpikir:</b>\n{e(think_txt[-350:])}</blockquote>"
                                self.edit_message(
                                    self.allowed_chat_id,
                                    info["msg_id"],
                                    f"╭─── {spin} <b>OPENCODE SEDANG BEKERJA</b> ───╮\n"
                                    f"│ ⏱️ <b>Waktu  :</b> <code>{elapsed}s [{make_progress_bar(elapsed)}]</code>\n"
                                    f"│ 💬 <b>Prompt :</b> <code>{e(info['prompt'][:140])}</code>\n"
                                    f"╰────────────────────────────────────╯{extra_live}",
                                )
                    con.close()
                except Exception:
                    pass

    def open_prompt_launchpad(self, chat_id: str, prompt: str, attached_file: str = "") -> None:
        pad_id = uuid.uuid4().hex[:8]
        if len(self.pending_launchpads) > 20:
            oldest = next(iter(self.pending_launchpads))
            self.pending_launchpads.pop(oldest, None)

        self.pending_launchpads[pad_id] = {
            "prompt": prompt,
            "attached_file": attached_file,
        }
        text, kb = self.build_launchpad_text_and_kb(pad_id)
        self.send_message(chat_id, text, reply_markup=kb)

    def queue_or_run_agent(
        self,
        chat_id: str,
        agent_key: str,
        prompt: str,
        workspace: str,
        attached_file: str = "",
        force: bool = False,
    ) -> None:
        blocked, reason = is_protected_folder(workspace)
        if blocked:
            self.send_message(
                chat_id,
                f"⛔ <b>[Proteksi Keamanan Aktif]</b>\n{e(reason)}\n\n"
                "Silakan pilih folder project koding Anda terlebih dahulu melalui tombol di bawah:",
                reply_markup=self.build_projects_keyboard(),
            )
            return

        self.config = load_config()
        if not is_agent_installed(agent_key, self.config):
            self.send_message(
                chat_id,
                f"⚠️ <b>CLI Agent <code>{e(agent_key.upper())}</code> Belum Terinstal di Laptop!</b>\n\n"
                "Saat ini AI Agent yang terdeteksi siap di laptop Anda adalah:\n"
                "• 🟢 <b>OPENCODE</b> (OpenCode AI CLI)\n"
                "• 🟢 <b>AGY</b> (Google Antigravity CLI)\n\n"
                "Silakan pilih <b>OPENCODE</b> atau <b>AGY</b> di bawah:",
                reply_markup=self.build_agents_keyboard(),
            )
            return

        if not force and DANGEROUS_PATTERNS.search(prompt):
            conf_id = uuid.uuid4().hex[:8]
            self.pending_confirmations[conf_id] = {
                "type": "agent",
                "agent": agent_key,
                "prompt": prompt,
                "workspace": workspace,
                "attached_file": attached_file,
            }
            kb = {
                "inline_keyboard": [
                    [
                        {"text": "⚠️ Ya, Saya Yakin Jalankan", "callback_data": f"confirm_ok:{conf_id}"},
                        {"text": "❌ Batalkan", "callback_data": f"confirm_no:{conf_id}"},
                    ]
                ]
            }
            self.send_message(
                chat_id,
                "╭─── 🛡️ <b>KONFIRMASI KEAMANAN DATA</b> ───╮\n"
                "│ ⚠️ Terdeteksi kata sensitif (hapus/remove/reset)\n"
                f"│ 📂 <b>Folder:</b> <code>{e(workspace)}</code>\n"
                "╰────────────────────────────────────╯\n"
                f"<pre><code>{e(prompt)}</code></pre>\n"
                "Apakah Anda benar-benar yakin ingin menjalankan perintah ini?",
                reply_markup=kb,
            )
            return

        t = threading.Thread(
            target=self.run_agent_task,
            args=(chat_id, agent_key, prompt, workspace, attached_file),
            daemon=True,
        )
        t.start()

    def run_agent_task(self, chat_id: str, agent_key: str, prompt: str, workspace: str, attached_file: str = "") -> None:
        self.config = load_config()
        agents_cfg = self.config.get("agents", {})
        if agent_key not in agents_cfg:
            self.send_message(
                chat_id,
                f"❌ Agent <code>{e(agent_key)}</code> tidak ditemukan di config.json.\nKetik /agents untuk melihat daftar agent.",
            )
            return

        agent_info = agents_cfg[agent_key]
        agent_title = agent_info.get("name", agent_key)
        cmd_template = list(agent_info.get("command", []))

        effective_prompt = prompt
        if self.safe_mode:
            effective_prompt = (
                "[ATURAN KEAMANAN READ-ONLY AKTIF: Kamu DILARANG mengubah, membuat, atau menghapus file apa pun. "
                "Hanya baca kode/analisis dan jawab pertanyaan berikut secara langsung] " + prompt
            )

        file_flag = agent_info.get("file_flag", "")
        if attached_file and not file_flag:
            effective_prompt = f"[Lihat file lampiran di: {attached_file}] " + effective_prompt

        continue_flag = agent_info.get("continue_flag", "")
        model_flag = agent_info.get("model_flag", "")
        mode_flags = agent_info.get("readonly_flags" if self.safe_mode else "write_flags") or []

        resolved_bin = resolve_cli_executable(cmd_template[0]) if cmd_template else ""
        if not resolved_bin:
            self.send_message(chat_id, f"❌ Executable untuk <code>{e(agent_key)}</code> tidak ditemukan di PATH.")
            return

        extra_flags = []
        if mode_flags:
            extra_flags.extend(mode_flags)
        if self.continue_session and continue_flag:
            extra_flags.append(continue_flag)
        if self.active_model and model_flag and is_model_compatible_with_agent(self.active_model, agent_key):
            extra_flags.extend([model_flag, self.active_model])
        if attached_file and file_flag:
            extra_flags.extend([file_flag, attached_file])

        template_tail = []
        for part in cmd_template[1:]:
            if "{prompt}" in part:
                template_tail.append(part.replace("{prompt}", effective_prompt))
            else:
                template_tail.append(part)

        # Cari posisi penyisipan extra_flags yang sesuai sintaks CLI:
        # - Jika ada flag prompt (-p, --message, -q, dll) tepat sebelum prompt, taruh extra_flags SEBELUM flag tsb.
        # - Jika prompt adalah positional argument (misal: "opencode run ... [prompt]"), taruh extra_flags sebelum prompt.
        prompt_flags_set = {"-p", "--prompt", "--print", "-q", "--message"}
        insert_idx = len(template_tail)
        for i, token in enumerate(template_tail):
            if token == effective_prompt:
                if i > 0 and template_tail[i - 1] in prompt_flags_set:
                    insert_idx = i - 1
                else:
                    insert_idx = i
                break

        cmd_list = [resolved_bin] + template_tail[:insert_idx] + extra_flags + template_tail[insert_idx:]

        self.continue_session = True
        use_shell = os.name == "nt" and resolved_bin.lower().endswith((".cmd", ".bat", ".ps1"))

        with self.tasks_lock:
            self.task_counter += 1
            task_id = self.task_counter

        active_model_display = self.active_model if is_model_compatible_with_agent(self.active_model, agent_key) else "default"
        log_activity(f"🚀 MULAI Task #{task_id} [{agent_key} | {active_model_display}] ({self.mode_label()}) di '{workspace}' | Prompt: {prompt}")

        kill_markup = {
            "inline_keyboard": [[{"text": f"🛑 Hentikan Task #{task_id}", "callback_data": f"kill:{task_id}"}]]
        }

        self.send_chat_action(chat_id, "typing")
        attach_note = f"\n│ 📎 <b>File   :</b> <code>{e(os.path.basename(attached_file))}</code>" if attached_file else ""
        model_note = f"\n│ 🧠 <b>Model  :</b> <code>{e(active_model_display)}</code>"
        status_msg_id = self.send_message(
            chat_id,
            f"╭─── 🧠💭 <b>TASK #{task_id}: {e(agent_key.upper())} BEKERJA</b> ───╮\n"
            f"│ ⏱️ <b>Waktu  :</b> <code>0s [{make_progress_bar(0)}]</code>\n"
            f"│ 🛡️ <b>Mode   :</b> <code>{e(self.mode_label())}</code>{model_note}\n"
            f"│ 📂 <b>Folder :</b> <code>{e(workspace)}</code>{attach_note}\n"
            "╰─────────────────────────────────────╯\n"
            f"💬 <b>Prompt:</b> <i>\"{e(prompt[:160])}\"</i>\n\n"
            "⚙️ <code>Menginisialisasi AI & menyusun penalaran...</code>",
            reply_markup=kill_markup,
        )

        start_ts = time.time()
        start_ms = int(start_ts * 1000) - 1000
        last_output_ts = start_ts
        hang_alert_sent = False
        output_lines = []
        thinking_lines = []
        output_lock = threading.Lock()

        try:
            proc = subprocess.Popen(
                cmd_list,
                cwd=workspace,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=use_shell,
            )
            with self.tasks_lock:
                self.running_tasks[task_id] = {
                    "agent": agent_key,
                    "prompt": prompt,
                    "process": proc,
                    "start_time": start_ts,
                    "workspace": workspace,
                }

            def _reader():
                nonlocal last_output_ts
                try:
                    for raw_line in proc.stdout:
                        clean_line = strip_ansi(raw_line)
                        with output_lock:
                            last_output_ts = time.time()
                            if clean_line.lstrip().startswith("Thinking:"):
                                thinking_lines.append(clean_line.lstrip()[9:].strip())
                            else:
                                output_lines.append(clean_line)
                except Exception:
                    pass

            reader_thread = threading.Thread(target=_reader, daemon=True)
            reader_thread.start()

            tick = 0
            while proc.poll() is None:
                time.sleep(2.8)
                if proc.poll() is not None:
                    break
                tick += 1
                now = time.time()
                elapsed = int(now - start_ts)
                spin = SPINNERS[tick % len(SPINNERS)]
                self.send_chat_action(chat_id, "typing")

                if not hang_alert_sent and (now - last_output_ts) > 600:
                    hang_alert_sent = True
                    self.send_message(
                        chat_id,
                        f"⚠️ <b>Peringatan:</b> Task #{task_id} ({e(agent_title)}) sudah berjalan <code>{elapsed}s</code> tanpa output baru.",
                        reply_markup=kill_markup,
                    )

                live_think = ""
                live_tool = ""
                live_ans = ""
                if agent_key == "opencode":
                    db_think, db_tool, db_ans = get_latest_opencode_thinking(since_ms=start_ms)
                    live_think = db_think
                    live_tool = db_tool
                    live_ans = db_ans

                with output_lock:
                    if not live_think and thinking_lines:
                        live_think = " ".join(thinking_lines)
                    recent_stdout = clean_agent_stdout("".join(output_lines[-6:]))

                status_blocks = []
                if live_tool:
                    status_blocks.append(f"🔧 <b>Tool Aktif:</b> <code>{e(live_tool)}</code>")
                if live_think:
                    status_blocks.append(f"<blockquote expandable>💭 <b>AI Sedang Berpikir:</b>\n{e(live_think[-400:])}</blockquote>")
                elif not recent_stdout and not live_ans:
                    status_blocks.append("💭 <code>AI sedang menganalisis & menyusun penalaran...</code>")

                if live_ans:
                    status_blocks.append(f"✍️ <b>Menyusun Jawaban:</b>\n<pre><code>{e(live_ans[-300:])}</code></pre>")
                elif recent_stdout:
                    status_blocks.append(f"📡 <b>Live Terminal Output:</b>\n<pre><code>{e(recent_stdout[-300:])}</code></pre>")

                live_section = "\n\n" + "\n\n".join(status_blocks) if status_blocks else ""

                live_text = (
                    f"╭─── {spin} <b>TASK #{task_id}: {e(agent_key.upper())} BEKERJA</b> ───╮\n"
                    f"│ ⏱️ <b>Waktu  :</b> <code>{elapsed}s [{make_progress_bar(elapsed)}]</code>\n"
                    f"│ 🛡️ <b>Mode   :</b> <code>{e(self.mode_label())}</code>{model_note}\n"
                    f"│ 📂 <b>Folder :</b> <code>{e(workspace)}</code>{attach_note}\n"
                    "╰─────────────────────────────────────╯\n"
                    f"💬 <b>Prompt:</b> <i>\"{e(prompt[:160])}\"</i>"
                    f"{live_section}"
                )
                self.edit_message(chat_id, status_msg_id, live_text, reply_markup=kill_markup)

            reader_thread.join(timeout=2)
            exit_code = proc.returncode
        except Exception as exc:
            duration = round(time.time() - start_ts, 1)
            with self.tasks_lock:
                self.running_tasks.pop(task_id, None)
            self.delete_message(chat_id, status_msg_id)
            self.send_message(
                chat_id,
                f"❌ <b>[Task #{task_id}] Gagal menjalankan '{e(agent_key)}' ({duration}s)</b>\n"
                f"<pre><code>{e(str(exc))}</code></pre>",
            )
            return

        duration = round(time.time() - start_ts, 1)
        with self.tasks_lock:
            self.running_tasks.pop(task_id, None)

        self.delete_message(chat_id, status_msg_id)

        icon = "✅" if exit_code == 0 else "⚠️"
        with output_lock:
            stdout_data = "".join(output_lines)
            think_summary = " ".join(thinking_lines).strip()

        output_clean = clean_agent_stdout(stdout_data)

        # Untuk OpenCode, ambil jawaban & proses berpikir yang 100% bersih langsung dari SQLite DB jika tersedia
        if agent_key == "opencode":
            db_think, _, db_ans = get_latest_opencode_thinking(since_ms=start_ms)
            if db_think:
                think_summary = db_think
            if db_ans and exit_code == 0:
                output_clean = db_ans

        if not output_clean:
            output_clean = "(Selesai tanpa output teks di terminal)"

        log_activity(f"{icon} SELESAI Task #{task_id} [{agent_key}] ({duration}s) | Hasil:\n{output_clean[:500]}\n" + "-" * 50)

        git_info = get_git_changes_summary_html(workspace)
        think_card = (
            f"<blockquote expandable>💭 <b>Proses Berpikir AI (Tap untuk buka/tutup):</b>\n{e(think_summary[:600])}</blockquote>\n\n"
            if think_summary
            else ""
        )
        header = (
            f"╭─── {icon} <b>TASK #{task_id} SELESAI ({duration}s)</b> ───╮\n"
            f"│ 🤖 <b>Agent  :</b> <code>{e(agent_title)}</code>{model_note}\n"
            f"│ 🛡️ <b>Mode   :</b> <code>{e(self.mode_label())}</code>\n"
            f"│ 📂 <b>Folder :</b> <code>{e(workspace)}</code>\n"
            f"│ 💬 <b>Prompt :</b> <code>{e(prompt[:120])}</code>\n"
            "╰─────────────────────────────────────╯\n\n"
            f"{think_card}"
        )

        if len(output_clean) > 2200:
            short_out = md_to_tg_html(output_clean[:1800]) + "\n\n📎 <i>[Output lengkap dilampirkan sebagai file .txt di bawah]</i>"
            self.send_message(
                chat_id,
                header + short_out + git_info,
                reply_markup=self.default_action_buttons(),
            )
            self.send_document_content(
                chat_id,
                f"Task_{task_id}_{agent_key}_output.txt",
                output_clean,
                caption=f"📄 Output lengkap Task #{task_id} ({agent_title})",
            )
        else:
            self.send_message(
                chat_id,
                header + md_to_tg_html(output_clean) + git_info,
                reply_markup=self.default_action_buttons(),
            )

    def handle_screenshot(self, chat_id: str) -> None:
        self.send_chat_action(chat_id, "upload_photo")
        ss_path = BASE_DIR / f"screenshot_{int(time.time())}.png"
        try:
            ok = capture_laptop_screenshot(ss_path)
            if ok and ss_path.exists():
                ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
                self.send_binary_file(
                    chat_id,
                    "photo",
                    "sendPhoto",
                    ss_path,
                    caption=f"📸 Tangkapan Layar Laptop ({ts_str})\n📂 Workspace: {self.active_workspace}",
                )
            else:
                self.send_message(
                    chat_id,
                    "⚠️ <b>Gagal mengambil screenshot layar laptop.</b>\n"
                    "Layar kemungkinan sedang terkunci (Lock Screen / Win+L) atau monitor dalam keadaan mati.",
                )
        finally:
            ss_path.unlink(missing_ok=True)

    def handle_callback_query(self, cb: dict) -> None:
        cb_id = cb.get("id")
        data = cb.get("data", "")
        msg = cb.get("message") or {}
        msg_id = msg.get("message_id", 0)
        chat_id = str((msg.get("chat") or {}).get("id", ""))

        if not chat_id or (self.allowed_chat_id and chat_id != self.allowed_chat_id):
            return

        self.api_call("answerCallbackQuery", {"callback_query_id": cb_id}, timeout=5)

        # --- Handler untuk Interactive File Explorer (fexp_*) ---
        if data.startswith("cb:files:"):
            page_s = data.split(":", 2)[2]
            page = int(page_s) if page_s.isdigit() else 0
            txt, kb = self.build_file_explorer_ui(page=page)
            self.edit_message(chat_id, msg_id, txt, reply_markup=kb)
            return

        if data == "fexp_up":
            parent_dir = str(Path(self.active_workspace).parent)
            blocked, reason = is_protected_folder(parent_dir)
            if blocked:
                self.send_message(chat_id, f"⛔ <b>[Proteksi Keamanan]</b>\n{e(reason)}")
                return
            self.active_workspace = parent_dir
            self.continue_session = False
            self.config["default_workspace"] = parent_dir
            save_config(self.config)
            txt, kb = self.build_file_explorer_ui(page=0)
            self.edit_message(chat_id, msg_id, txt, reply_markup=kb)
            return

        if data.startswith("fexp_dl:"):
            idx_s = data.split(":", 1)[1]
            if idx_s.isdigit():
                idx = int(idx_s)
                if 0 <= idx < len(self.explorer_entries):
                    chosen_path = Path(self.explorer_entries[idx])
                    if chosen_path.is_file():
                        self.send_chat_action(chat_id, "upload_document")
                        self.send_binary_file(
                            chat_id,
                            "document",
                            "sendDocument",
                            chosen_path,
                            caption=f"📥 File: {chosen_path.name}\n📂 Lokasi: {chosen_path.parent}",
                        )
            return

        if data.startswith("fexp_open:"):
            idx_s = data.split(":", 1)[1]
            if idx_s.isdigit():
                idx = int(idx_s)
                if 0 <= idx < len(self.explorer_entries):
                    chosen_path = Path(self.explorer_entries[idx])
                    if chosen_path.is_dir():
                        blocked, reason = is_protected_folder(str(chosen_path))
                        if blocked:
                            self.send_message(chat_id, f"⛔ <b>[Proteksi Keamanan]</b>\n{e(reason)}")
                            return
                        self.active_workspace = str(chosen_path)
                        self.continue_session = False
                        self.config["default_workspace"] = str(chosen_path)
                        save_config(self.config)
                        txt, kb = self.build_file_explorer_ui(page=0)
                        self.edit_message(chat_id, msg_id, txt, reply_markup=kb)
                    elif chosen_path.is_file():
                        suffix_low = chosen_path.suffix.lower()
                        if suffix_low in IMAGE_EXTENSIONS:
                            self.send_chat_action(chat_id, "upload_photo")
                            self.send_binary_file(
                                chat_id,
                                "photo",
                                "sendPhoto",
                                chosen_path,
                                caption=f"🖼️ {chosen_path.name}\n📂 {chosen_path.parent}",
                            )
                            return
                        if suffix_low in BINARY_EXTENSIONS:
                            self.send_chat_action(chat_id, "upload_document")
                            self.send_binary_file(
                                chat_id,
                                "document",
                                "sendDocument",
                                chosen_path,
                                caption=f"📦 File Biner/Dokumen: {chosen_path.name}",
                            )
                            return
                        try:
                            raw_content = chosen_path.read_text(encoding="utf-8", errors="replace")
                            ext = chosen_path.suffix.lstrip(".") or "txt"
                            preview = raw_content[:2500]
                            more_note = "\n<i>... (File dipotong, klik tombol Download di bawah untuk file utuh)</i>" if len(raw_content) > 2500 else ""
                            file_view = (
                                "╭─── 📄 <b>FILE VIEWER</b> ───╮\n"
                                f"│ 📄 <b>Nama :</b> <code>{e(chosen_path.name)}</code>\n"
                                f"│ 📂 <b>Path :</b> <code>{e(str(chosen_path.parent))}</code>\n"
                                "╰──────────────────────────╯\n"
                                f"<pre><code class=\"language-{e(ext)}\">{e(preview)}</code></pre>{more_note}"
                            )
                            kb = {
                                "inline_keyboard": [
                                    [
                                        {"text": "📥 Download File Ini", "callback_data": f"fexp_dl:{idx}"},
                                    ],
                                    [
                                        {"text": "🔙 Kembali ke File Explorer", "callback_data": "cb:files:0"},
                                        {"text": "🏠 Menu Utama", "callback_data": "cb:home"},
                                    ],
                                ]
                            }
                            self.edit_message(chat_id, msg_id, file_view, reply_markup=kb)
                        except Exception as exc:
                            self.send_message(chat_id, f"⚠️ Tidak dapat membaca file: <code>{e(exc)}</code>")
            return

        # --- Handler untuk Interactive Prompt Launchpad (pad_*) ---
        if data.startswith("pad_run:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                _, pad_id, chosen_agent = parts
                self.config = load_config()
                if not is_agent_installed(chosen_agent, self.config):
                    self.send_message(
                        chat_id,
                        f"⚠️ <b>CLI Agent <code>{e(chosen_agent.upper())}</code> belum terinstal di laptop Anda!</b>\n"
                        "Silakan klik tombol <b>⭐/🟢 OPENCODE</b> atau <b>🟢 AGY</b> pada kartu konfirmasi di atas.",
                    )
                    return
                pad = self.pending_launchpads.pop(pad_id, None)
                if not pad:
                    self.edit_message(chat_id, msg_id, "ℹ️ Sesi konfirmasi prompt ini sudah selesai atau kadaluarsa.")
                    return
                self.active_agent = chosen_agent
                self.config["default_agent"] = chosen_agent
                save_config(self.config)
                self.delete_message(chat_id, msg_id)
                self.queue_or_run_agent(
                    chat_id,
                    chosen_agent,
                    pad["prompt"],
                    self.active_workspace,
                    attached_file=pad.get("attached_file", ""),
                )
            return

        if data.startswith("pad_cancel:"):
            pad_id = data.split(":", 1)[1]
            self.pending_launchpads.pop(pad_id, None)
            self.edit_message(chat_id, msg_id, "🛑 <b>Eksekusi prompt dibatalkan.</b>")
            return

        if data.startswith("pad_mode:"):
            pad_id = data.split(":", 1)[1]
            self.safe_mode = not self.safe_mode
            self.config["safe_mode"] = self.safe_mode
            save_config(self.config)
            if pad_id in self.pending_launchpads:
                txt, kb = self.build_launchpad_text_and_kb(pad_id)
                self.edit_message(chat_id, msg_id, txt, reply_markup=kb)
            return

        if data.startswith("pad_models:"):
            parts = data.split(":")
            pad_id = parts[1]
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            self.cached_models = fetch_available_models(self.active_agent)
            self.edit_message(
                chat_id,
                msg_id,
                f"╭─── 🧠 <b>PILIH MODEL AI ({e(self.active_agent.upper())})</b> ───╮\n│ Model Aktif: <code>{e(self.active_model)}</code>\n╰──────────────────────────────────╯",
                reply_markup=self.build_models_keyboard(page=page, pad_id=pad_id),
            )
            return

        if data.startswith("pad_refm:"):
            pad_id = data.split(":", 1)[1]
            self.cached_models = fetch_available_models(self.active_agent)
            self.edit_message(
                chat_id,
                msg_id,
                f"✅ <b>Daftar model {e(self.active_agent.upper())} di-refresh ({len(self.cached_models)} model)!</b>\n🧠 Saat ini: <code>{e(self.active_model)}</code>",
                reply_markup=self.build_models_keyboard(page=0, pad_id=pad_id),
            )
            return

        if data.startswith("pad_setm:"):
            parts = data.split(":")
            pad_id = parts[1]
            idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            if 0 <= idx < len(self.cached_models):
                self.active_model = self.cached_models[idx]
                self.config["default_model"] = self.active_model
                save_config(self.config)
            if pad_id in self.pending_launchpads:
                txt, kb = self.build_launchpad_text_and_kb(pad_id)
                self.edit_message(chat_id, msg_id, txt, reply_markup=kb)
            return

        if data.startswith("pad_projects:"):
            pad_id = data.split(":", 1)[1]
            self.edit_message(
                chat_id,
                msg_id,
                f"╭─── 📂 <b>PILIH FOLDER PROJECT</b> ───╮\n│ Aktif: <code>{e(self.active_workspace)}</code>\n╰───────────────────────────────╯",
                reply_markup=self.build_projects_keyboard(pad_id=pad_id),
            )
            return

        if data.startswith("pad_setp:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                _, pad_id, proj_key = parts
                all_projs = discover_all_projects(self.config)
                if proj_key in all_projs:
                    self.active_workspace = all_projs[proj_key]
                    self.continue_session = False
                    self.config["default_workspace"] = self.active_workspace
                    save_config(self.config)
                if pad_id in self.pending_launchpads:
                    txt, kb = self.build_launchpad_text_and_kb(pad_id)
                    self.edit_message(chat_id, msg_id, txt, reply_markup=kb)
            return

        if data.startswith("pad_back:"):
            pad_id = data.split(":", 1)[1]
            if pad_id in self.pending_launchpads:
                txt, kb = self.build_launchpad_text_and_kb(pad_id)
                self.edit_message(chat_id, msg_id, txt, reply_markup=kb)
            return

        # --- Handler Menu Standar ---
        if data == "cb:home":
            self.handle_command(chat_id, "/help")
            return

        if data.startswith("kill:"):
            tid_str = data.split(":", 1)[1]
            self.handle_command(chat_id, f"/kill {tid_str}")

        elif data.startswith("set_agent:"):
            target = data.split(":", 1)[1]
            self.handle_command(chat_id, f"/agent {target}")

        elif data.startswith("set_proj:"):
            proj = data.split(":", 1)[1]
            self.handle_command(chat_id, f"/cd {proj}")

        elif data.startswith("cb:menu_models"):
            parts = data.split(":")
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            if page == 0:
                self.cached_models = fetch_available_models(self.active_agent)
            self.edit_message(
                chat_id,
                msg_id,
                f"╭─── 🧠 <b>DAFTAR MODEL AI ({e(self.active_agent.upper())})</b> ───╮\n│ Model Aktif: <code>{e(self.active_model)}</code>\n╰──────────────────────────────────╯\nTap salah satu model di bawah untuk mengaktifkan:",
                reply_markup=self.build_models_keyboard(page=page),
            )

        elif data == "cb:refresh_models":
            self.cached_models = fetch_available_models(self.active_agent)
            self.edit_message(
                chat_id,
                msg_id,
                f"✅ <b>Daftar model {e(self.active_agent.upper())} diperbarui ({len(self.cached_models)} model)!</b>\n🧠 Model Aktif: <code>{e(self.active_model)}</code>",
                reply_markup=self.build_models_keyboard(page=0),
            )

        elif data.startswith("set_model:"):
            idx_str = data.split(":", 1)[1]
            if idx_str.isdigit():
                idx = int(idx_str)
                if 0 <= idx < len(self.cached_models):
                    self.active_model = self.cached_models[idx]
                    self.config["default_model"] = self.active_model
                    save_config(self.config)
                    self.edit_message(
                        chat_id,
                        msg_id,
                        f"✅ <b>Model AI Berhasil Diganti!</b>\n🧠 Model Aktif: <code>{e(self.active_model)}</code>",
                        reply_markup=self.default_action_buttons(),
                    )

        elif data == "cb:new_session":
            self.handle_command(chat_id, "/new")

        elif data == "cb:screenshot":
            threading.Thread(target=self.handle_screenshot, args=(chat_id,), daemon=True).start()

        elif data == "cb:toggle_mode":
            self.safe_mode = not self.safe_mode
            self.config["safe_mode"] = self.safe_mode
            save_config(self.config)
            desc = (
                "🟢 <b>Mode AMAN (Plan / Read-Only) AKTIF.</b>\nAI berjalan dalam mode Plan/Read-Only dan dilarang mengubah/menghapus file."
                if self.safe_mode
                else "🔴 <b>Mode EDIT (Build / Write) AKTIF.</b>\nAI sekarang diizinkan membuat & mengedit file di folder project aktif."
            )
            self.send_message(chat_id, f"🛡️ <b>Status Keamanan Diperbarui:</b>\n{desc}", reply_markup=self.default_action_buttons())

        elif data == "cb:ask_undo":
            kb = {
                "inline_keyboard": [
                    [
                        {"text": "⏪ Ya, Kembalikan File (Git Checkout)", "callback_data": "cb:do_undo"},
                        {"text": "❌ Batal", "callback_data": "cb:cancel_undo"},
                    ]
                ]
            }
            self.send_message(
                chat_id,
                f"⚠️ <b>Konfirmasi Undo (Git Restore)</b>\nApakah Anda ingin membatalkan semua editan yang belum di-commit di folder:\n<code>{e(self.active_workspace)}</code>?",
                reply_markup=kb,
            )

        elif data == "cb:do_undo":
            try:
                res = subprocess.run(
                    ["git", "checkout", "--", "."],
                    cwd=self.active_workspace,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=10,
                )
                if res.returncode == 0:
                    self.edit_message(chat_id, msg_id, f"✅ <b>Berhasil!</b> Semua perubahan file di <code>{e(self.active_workspace)}</code> telah dikembalikan ke kondisi semula.")
                else:
                    self.edit_message(chat_id, msg_id, f"⚠️ Gagal melakukan git restore:\n<pre><code>{e(res.stdout)}</code></pre>")
            except Exception as e_err:
                self.edit_message(chat_id, msg_id, f"❌ Error: <code>{e(e_err)}</code>")

        elif data == "cb:cancel_undo":
            self.edit_message(chat_id, msg_id, "ℹ️ Undo dibatalkan. Perubahan file tetap disimpan.")

        elif data.startswith("confirm_ok:"):
            conf_id = data.split(":", 1)[1]
            item = self.pending_confirmations.pop(conf_id, None)
            if not item:
                self.edit_message(chat_id, msg_id, "ℹ️ Konfirmasi ini sudah kadaluarsa atau selesai.")
                return
            self.edit_message(chat_id, msg_id, f"✅ <b>Dikonfirmasi!</b> Menjalankan perintah: <code>{e(item['prompt'])}</code>")
            if item["type"] == "agent":
                self.queue_or_run_agent(
                    chat_id,
                    item["agent"],
                    item["prompt"],
                    item["workspace"],
                    item.get("attached_file", ""),
                    force=True,
                )
            elif item["type"] == "cmd":
                self._execute_shell_cmd(chat_id, item["prompt"])

        elif data.startswith("confirm_no:"):
            conf_id = data.split(":", 1)[1]
            self.pending_confirmations.pop(conf_id, None)
            self.edit_message(chat_id, msg_id, "🛑 <b>Perintah berbahaya berhasil dibatalkan.</b> Data Anda tetap aman!")

        elif data == "cb:menu_agents":
            self.handle_command(chat_id, "/agents")

        elif data == "cb:menu_projects":
            self.handle_command(chat_id, "/projects")

        elif data == "cb:sys":
            self.handle_command(chat_id, "/sys")

        elif data == "cb:status":
            self.handle_command(chat_id, "/cmd git status")

        elif data == "cb:diff":
            try:
                res = subprocess.run(
                    ["git", "diff"],
                    cwd=self.active_workspace,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                )
                diff_txt = strip_ansi(res.stdout or "").strip()
                if not diff_txt:
                    res_stat = subprocess.run(
                        ["git", "status", "--short"],
                        cwd=self.active_workspace,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=10,
                    )
                    diff_txt = strip_ansi(res_stat.stdout or "").strip() or "Tidak ada perubahan git (working tree clean)."
                if len(diff_txt) > 3000:
                    self.send_document_content(
                        chat_id,
                        "changes.diff",
                        diff_txt,
                        caption=f"📄 Git Diff lengkap di {self.active_workspace}",
                    )
                else:
                    self.send_message(
                        chat_id,
                        f"╭─── 📄 <b>GIT DIFF VIEWER</b> ───╮\n│ 📂 <code>{e(self.active_workspace)}</code>\n╰──────────────────────────╯\n<pre><code class=\"language-diff\">{e(diff_txt)}</code></pre>",
                        reply_markup=self.default_action_buttons(),
                    )
            except Exception as exc:
                self.send_message(chat_id, f"⚠️ Gagal menjalankan git diff: <code>{e(exc)}</code>")

    def _execute_shell_cmd(self, chat_id: str, arg: str) -> None:
        if arg.strip().lower() in ("dir", "ls", "ls -la", "ls -l"):
            txt, kb = self.build_file_explorer_ui(page=0)
            self.send_message(chat_id, txt, reply_markup=kb)
            return

        try:
            self.send_chat_action(chat_id, "typing")
            res = subprocess.run(
                arg,
                cwd=self.active_workspace,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                timeout=60,
            )
            out = strip_ansi(res.stdout or "").strip() or "(Selesai tanpa output)"
            status_badge = "✅ 0 (Sukses)" if res.returncode == 0 else f"⚠️ {res.returncode} (Error)"
            header = (
                "╭─── 💻 <b>TERMINAL CONSOLE UI</b> ───╮\n"
                f"│ 📂 <b>Folder :</b> <code>{e(self.active_workspace)}</code>\n"
                f"│ ⚡ <b>Cmd    :</b> <code>{e(arg)}</code>\n"
                f"│ 🏁 <b>Status :</b> <code>{status_badge}</code>\n"
                "╰──────────────────────────────╯\n"
            )
            if len(out) > 2800:
                short_out = f"<pre><code>{e(out[:2000])}</code></pre>\n📎 <i>Output lengkap terlampir di file cmd_output.txt</i>"
                self.send_message(chat_id, header + short_out, reply_markup=self.default_action_buttons())
                self.send_document_content(
                    chat_id,
                    "cmd_output.txt",
                    out,
                    caption=f"💻 Output lengkap `{arg}` (Exit {res.returncode})",
                )
            else:
                self.send_message(
                    chat_id,
                    header + f"<pre><code>{e(out)}</code></pre>",
                    reply_markup=self.default_action_buttons(),
                )
        except Exception as exc:
            self.send_message(chat_id, f"❌ Gagal menjalankan perintah: <code>{e(exc)}</code>")

    def handle_command(self, chat_id: str, text: str) -> None:
        parts = text.strip().split(maxsplit=1)
        cmd = parts[0].lower().split("@")[0]
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/start", "/help"):
            self.config = load_config()
            help_text = (
                "╭─── 🤖 <b>UNIVERSAL AI AGENT HUB</b> ───╮\n"
                f"│ 🛡️ <b>Mode    :</b> <code>{e(self.mode_label())}</code>\n"
                f"│ 🤖 <b>Agent   :</b> <code>{e(self.active_agent.upper())}</code>\n"
                f"│ 🧠 <b>Model   :</b> <code>{e(self.active_model)}</code>\n"
                f"│ 📂 <b>Project :</b> <code>{e(self.active_workspace)}</code>\n"
                f"│ 💬 <b>Memori  :</b> <code>{'Nyambung (-c)' if self.continue_session else 'Topik Baru'}</code>\n"
                "╰─────────────────────────────────╯\n\n"
                "✨ <b>Panduan Navigasi UI:</b>\n"
                "• <b>Ketik pesan biasa / kirim foto</b> ➡️ Membuka <i>Kartu Launchpad</i> untuk memilih Agent/Model/Project.\n"
                "• <b>Tap tombol di bawah</b> untuk menjelajahi file project (<i>GUI File Explorer</i>), ganti Model, ganti Project, atau cek status Laptop!"
            )
            self.send_message(chat_id, help_text, reply_markup=self.default_action_buttons())

        elif cmd in ("/files", "/dir", "/ls"):
            txt, kb = self.build_file_explorer_ui(page=0)
            self.send_message(chat_id, txt, reply_markup=kb)

        elif cmd in ("/models", "/model"):
            if arg:
                self.active_model = arg.strip()
                self.config["default_model"] = self.active_model
                save_config(self.config)
                self.send_message(
                    chat_id,
                    f"✅ <b>Model AI berhasil diset ke:</b> <code>{e(self.active_model)}</code>",
                    reply_markup=self.default_action_buttons(),
                )
                return
            self.cached_models = fetch_available_models(self.active_agent)
            self.send_message(
                chat_id,
                f"╭─── 🧠 <b>DAFTAR MODEL AI ({e(self.active_agent.upper())})</b> ───╮\n│ Model Aktif: <code>{e(self.active_model)}</code>\n╰──────────────────────────────────╯\nTap salah satu tombol di bawah untuk mengganti model:",
                reply_markup=self.build_models_keyboard(page=0),
            )

        elif cmd == "/new":
            self.continue_session = False
            self.send_message(
                chat_id,
                "🧹 <b>Sesi Percakapan Baru Siap!</b>\nChat Anda berikutnya akan memulai topik/sesi baru yang segar.",
                reply_markup=self.default_action_buttons(),
            )

        elif cmd in ("/ss", "/screenshot"):
            threading.Thread(target=self.handle_screenshot, args=(chat_id,), daemon=True).start()

        elif cmd == "/mode":
            self.safe_mode = not self.safe_mode
            self.config["safe_mode"] = self.safe_mode
            save_config(self.config)
            self.send_message(
                chat_id,
                f"🛡️ <b>Mode Keamanan sekarang:</b> <code>{e(self.mode_label())}</code>",
                reply_markup=self.default_action_buttons(),
            )

        elif cmd == "/sys":
            self.send_chat_action(chat_id, "typing")
            self.send_message(chat_id, get_system_health_html(), reply_markup=self.default_action_buttons())

        elif cmd == "/agents":
            self.config = load_config()
            lines = [
                "╭─── 🤖 <b>PILIH AI AGENT DEFAULT</b> ───╮",
                f"│ Agent Aktif: <code>{e(self.active_agent.upper())}</code>",
                "╰─────────────────────────────────╯",
            ]
            for k, v in self.config.get("agents", {}).items():
                installed = is_agent_installed(k, self.config)
                if k == self.active_agent and installed:
                    marker = "✅"
                    status_tag = "<i>(Aktif & Siap)</i>"
                elif installed:
                    marker = "🟢"
                    status_tag = "<i>(Terinstal)</i>"
                else:
                    marker = "⚪"
                    status_tag = "<i>(Belum Terinstal di PC)</i>"
                lines.append(f"{marker} <b>{e(k.upper())}</b> — {e(v.get('name'))} {status_tag}")
            self.send_message(chat_id, "\n".join(lines), reply_markup=self.build_agents_keyboard())

        elif cmd == "/agent":
            self.config = load_config()
            if not arg:
                self.send_message(
                    chat_id,
                    f"ℹ️ <b>Agent aktif saat ini:</b> <code>{e(self.active_agent.upper())}</code>\nTap tombol di bawah untuk mengganti agent:",
                    reply_markup=self.build_agents_keyboard(),
                )
                return

            arg_parts = arg.strip().split(maxsplit=1)
            target = arg_parts[0].lower().strip()
            extra_prompt = arg_parts[1].strip() if len(arg_parts) > 1 else ""

            if target not in self.config.get("agents", {}):
                self.send_message(chat_id, f"❌ Agent <code>{e(target)}</code> belum terdaftar di config.json.")
                return
            if not is_agent_installed(target, self.config):
                self.send_message(
                    chat_id,
                    f"⚠️ <b>CLI untuk Agent <code>{e(target.upper())}</code> belum terinstal di laptop Anda!</b>\n"
                    f"Agent aktif tetap: <code>{e(self.active_agent.upper())}</code>.\n\n"
                    "Silakan pilih <b>🟢 OPENCODE</b> atau <b>🟢 AGY</b>.",
                    reply_markup=self.build_agents_keyboard(),
                )
                return

            self.active_agent = target
            self.config["default_agent"] = target
            self.cached_models = fetch_available_models(self.active_agent)
            if not is_model_compatible_with_agent(self.active_model, self.active_agent) and self.cached_models:
                self.active_model = self.cached_models[0]
                self.config["default_model"] = self.active_model
            save_config(self.config)
            self.send_message(
                chat_id,
                f"✅ <b>Agent aktif berhasil diganti ke:</b> <code>{e(target.upper())}</code> ({e(self.config['agents'][target].get('name'))})\n"
                f"🧠 <b>Model aktif:</b> <code>{e(self.active_model)}</code>",
                reply_markup=self.default_action_buttons(),
            )

            if extra_prompt:
                self.queue_or_run_agent(chat_id, self.active_agent, extra_prompt, self.active_workspace)

        elif cmd == "/ask":
            ask_parts = arg.split(maxsplit=1)
            if len(ask_parts) < 2:
                self.send_message(chat_id, "⚠️ Format: <code>/ask &lt;kode_agent&gt; &lt;prompt&gt;</code>\nContoh: <code>/ask opencode halo 1+1 berapa?</code>")
                return
            target_agent, prompt_text = ask_parts[0].lower(), ask_parts[1]
            self.queue_or_run_agent(chat_id, target_agent, prompt_text, self.active_workspace)

        elif cmd == "/projects":
            self.config = load_config()
            all_projs = discover_all_projects(self.config)
            text_ui = (
                "╭─── 📂 <b>PROJECT WORKSPACE MANAGER</b> ───╮\n"
                f"│ 📍 <b>Aktif :</b> <code>{e(self.active_workspace)}</code>\n"
                f"│ 🔍 <b>Total :</b> <code>{len(all_projs)} Folder Project Terdeteksi</code>\n"
                "╰────────────────────────────────────╯\n"
                "👇 <i>Tap salah satu tombol di bawah untuk pindah folder project:</i>"
            )
            self.send_message(chat_id, text_ui, reply_markup=self.build_projects_keyboard())

        elif cmd == "/cd":
            if not arg:
                txt, kb = self.build_file_explorer_ui(page=0)
                self.send_message(chat_id, txt, reply_markup=kb)
                return
            self.config = load_config()
            all_projs = discover_all_projects(self.config)
            target_path = all_projs.get(arg.lower(), arg.strip('"').strip("'"))
            resolved = os.path.abspath(os.path.expanduser(target_path))
            if not os.path.isdir(resolved):
                self.send_message(chat_id, f"❌ Folder tidak ditemukan: <code>{e(resolved)}</code>")
                return
            blocked, reason = is_protected_folder(resolved)
            if blocked:
                self.send_message(chat_id, f"⛔ <b>[Proteksi Keamanan]</b>\n{e(reason)}")
                return
            self.active_workspace = resolved
            self.continue_session = False
            self.config["default_workspace"] = resolved
            save_config(self.config)
            txt, kb = self.build_file_explorer_ui(page=0)
            self.send_message(chat_id, f"✅ <b>Workspace pindah ke:</b> <code>{e(self.active_workspace)}</code>\n\n" + txt, reply_markup=kb)

        elif cmd == "/addproject":
            proj_parts = arg.split(maxsplit=1)
            if len(proj_parts) < 2:
                self.send_message(chat_id, "⚠️ Format: <code>/addproject &lt;nama&gt; &lt;path_folder&gt;</code>")
                return
            name, raw_path = proj_parts[0].lower(), proj_parts[1].strip('"').strip("'")
            resolved = os.path.abspath(os.path.expanduser(raw_path))
            if not os.path.isdir(resolved):
                self.send_message(chat_id, f"❌ Folder tidak ditemukan di PC: <code>{e(resolved)}</code>")
                return
            blocked, reason = is_protected_folder(resolved)
            if blocked:
                self.send_message(chat_id, f"⛔ <b>[Proteksi Keamanan]</b>\n{e(reason)}")
                return
            self.config.setdefault("saved_projects", {})[name] = resolved
            save_config(self.config)
            self.send_message(
                chat_id,
                f"✅ Shortcut project <code>{e(name)}</code> disimpan untuk:\n<code>{e(resolved)}</code>",
                reply_markup=self.build_projects_keyboard(),
            )

        elif cmd == "/tasks":
            with self.tasks_lock:
                if not self.running_tasks:
                    self.send_message(chat_id, "✅ <b>Tidak ada task AI agent yang sedang berjalan saat ini.</b>", reply_markup=self.default_action_buttons())
                    return
                lines = ["╭─── ⏳ <b>TASK AI SEDANG BERJALAN</b> ───╮"]
                kb_rows = []
                now = time.time()
                for tid, info in self.running_tasks.items():
                    elapsed = round(now - info["start_time"], 1)
                    lines.append(
                        f"│ 🔹 <b>Task #{tid} [{e(info['agent'].upper())}]</b> (<code>{elapsed}s</code>)\n"
                        f"│    📂 <code>{e(info['workspace'])}</code>\n"
                        f"│    💬 <i>{e(info['prompt'][:80])}</i>"
                    )
                    kb_rows.append([{"text": f"🛑 Hentikan Task #{tid} ({info['agent']})", "callback_data": f"kill:{tid}"}])
                lines.append("╰──────────────────────────────────╯")
                self.send_message(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": kb_rows})

        elif cmd == "/kill":
            if not arg.isdigit():
                self.send_message(chat_id, "⚠️ Gunakan: <code>/kill &lt;nomor_task&gt;</code>")
                return
            tid = int(arg)
            with self.tasks_lock:
                task = self.running_tasks.get(tid)
                if not task:
                    self.send_message(chat_id, f"❌ Task #{tid} tidak ditemukan atau sudah selesai.")
                    return
                try:
                    task["process"].terminate()
                    self.send_message(chat_id, f"🛑 Sinyal berhenti dikirim ke <b>Task #{tid} ({e(task['agent'])})</b>.")
                except Exception as exc:
                    self.send_message(chat_id, f"⚠️ Gagal menghentikan Task #{tid}: <code>{e(exc)}</code>")

        elif cmd == "/cmd":
            if not arg:
                txt, kb = self.build_file_explorer_ui(page=0)
                self.send_message(chat_id, txt, reply_markup=kb)
                return
            if DANGEROUS_PATTERNS.search(arg):
                conf_id = uuid.uuid4().hex[:8]
                self.pending_confirmations[conf_id] = {
                    "type": "cmd",
                    "agent": "cmd",
                    "prompt": arg,
                    "workspace": self.active_workspace,
                }
                kb = {
                    "inline_keyboard": [
                        [
                            {"text": "⚠️ Ya, Jalankan Command", "callback_data": f"confirm_ok:{conf_id}"},
                            {"text": "❌ Batalkan", "callback_data": f"confirm_no:{conf_id}"},
                        ]
                    ]
                }
                self.send_message(
                    chat_id,
                    f"🛡️ <b>[Konfirmasi Perintah Terminal Berbahaya]</b>\nAnda akan menjalankan:\n<pre><code>{e(arg)}</code></pre>\ndi folder <code>{e(self.active_workspace)}</code>.\n\nYakin lanjutkan?",
                    reply_markup=kb,
                )
                return
            self._execute_shell_cmd(chat_id, arg)

        else:
            self.send_message(chat_id, "❓ Perintah tidak dikenal. Ketik /help untuk membuka Dashboard Utama.")

    def process_update(self, update: dict) -> None:
        if "callback_query" in update:
            self.handle_callback_query(update["callback_query"])
            return

        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id", ""))
        if not chat_id:
            return

        if not self.allowed_chat_id:
            self.allowed_chat_id = chat_id
            save_env_key("TELEGRAM_CHAT_ID", chat_id)
            print(f"✅ Auto-Paired! Chat ID Anda ({chat_id}) telah disimpan ke D:\\ai-bot\\.env")
            self.send_message(
                chat_id,
                f"🎉 <b>Berhasil Terhubung!</b>\nChat ID Anda (<code>{chat_id}</code>) otomatis disimpan ke .env.",
            )

        if chat_id != self.allowed_chat_id:
            print(f"⛔ Akses ditolak dari Chat ID asing: {chat_id}")
            return

        attached_path = ""
        if "photo" in msg and msg["photo"]:
            best_photo = msg["photo"][-1]
            fid = best_photo.get("file_id", "")
            attached_path = self.download_telegram_file(fid, f"photo_{int(time.time())}.jpg")
        elif "document" in msg and msg["document"]:
            doc = msg["document"]
            fid = doc.get("file_id", "")
            fname = doc.get("file_name", f"doc_{int(time.time())}")
            attached_path = self.download_telegram_file(fid, fname)

        text = (msg.get("text") or msg.get("caption") or "").strip()
        if attached_path and not text:
            text = "Tolong analisis gambar/file ini dan jelaskan atau perbaiki jika ada error."

        if not text:
            return

        if text.startswith("/") and not attached_path:
            self.handle_command(chat_id, text)
        else:
            self.open_prompt_launchpad(chat_id, text, attached_file=attached_path)

    def register_commands_menu(self) -> bool:
        commands = [
            {"command": "help", "description": "🏠 Buka Dashboard Utama & Kontrol Cepat"},
            {"command": "files", "description": "🗂️ Buka GUI File Explorer (Jelajahi Folder & File)"},
            {"command": "models", "description": "🧠 Pilih / ganti Model AI (tombol interaktif)"},
            {"command": "projects", "description": "📂 Pilih / pindah folder project (Auto-Scan)"},
            {"command": "agents", "description": "🤖 Pilih / ganti AI Agent default"},
            {"command": "new", "description": "🧹 Mulai topik/sesi percakapan baru"},
            {"command": "mode", "description": "🛡️ Ganti Mode 🟢 AMAN (Plan) vs 🔴 EDIT (Build)"},
            {"command": "ss", "description": "📸 Ambil screenshot layar laptop saat ini"},
            {"command": "sys", "description": "💻 Dashboard Kesehatan Laptop (Baterai, RAM, CPU)"},
            {"command": "tasks", "description": "⏳ Lihat & hentikan AI Agent yang sedang berjalan"},
        ]
        res = self.api_call("setMyCommands", {"commands": commands}, timeout=10)
        return bool(res.get("ok"))

    def start_polling(self) -> None:
        me = self.api_call("getMe", {}, timeout=10)
        if not me.get("ok"):
            print(f"❌ Token Bot tidak valid atau gagal terhubung ke Telegram: {me.get('error')}")
            sys.exit(1)

        self.register_commands_menu()
        self.start_session_watcher()
        start_windows_anti_sleep()

        bot_info = me.get("result", {})
        bot_username = bot_info.get("username", "UnknownBot")
        print("=" * 60)
        print(f"🤖 Bot Telegram Aktif: @{bot_username} (PID: {os.getpid()})")
        print(f"🎨 Rich Dashboard UI & GUI File Explorer : Aktif")
        print(f"🛡️ Mode Keamanan     : {self.mode_label()}")
        print(f"📂 Workspace Default : {self.active_workspace}")
        print(f"🧠 Agent & Model     : {self.active_agent} | {self.active_model}")
        if self.allowed_chat_id:
            print(f"🔒 Terkunci ke ChatID: {self.allowed_chat_id}")
        print("=" * 60)
        sys.stdout.flush()

        offset = 0
        initial = self.api_call("getUpdates", {"offset": 0, "timeout": 1}, timeout=10)
        if initial.get("ok") and initial.get("result"):
            updates = initial["result"]
            offset = updates[-1]["update_id"] + 1

        while True:
            try:
                res = self.api_call("getUpdates", {"offset": offset, "timeout": 25}, timeout=35)
                if res.get("ok"):
                    for item in res.get("result", []):
                        offset = item["update_id"] + 1
                        self.process_update(item)
                else:
                    time.sleep(3)
            except KeyboardInterrupt:
                print("\n🛑 Bot dihentikan oleh pengguna.")
                break
            except Exception as e_err:
                log_activity(f"⚠️ Polling error sementara ({e_err}), mencoba lagi dalam 5 detik...")
                time.sleep(5)


def interactive_setup_if_needed() -> tuple:
    env = load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or env.get("TELEGRAM_CHAT_ID", "")

    if not token:
        if not sys.stdin or not sys.stdin.isatty():
            while not token:
                time.sleep(5)
                env = load_env()
                token = env.get("TELEGRAM_BOT_TOKEN", "")
                chat_id = env.get("TELEGRAM_CHAT_ID", "")
            return token, chat_id

        print("=" * 60)
        print("🛠️  SETUP PERTAMA KALI — TELEGRAM AI AGENT BOT")
        print("=" * 60)
        token = input("👉 Paste Bot Token Anda di sini lalu tekan Enter: ").strip()
        if not token:
            sys.exit(1)
        save_env_key("TELEGRAM_BOT_TOKEN", token)

    return token, chat_id


if __name__ == "__main__":
    ensure_single_instance()
    bot_token, allowed_id = interactive_setup_if_needed()
    while True:
        try:
            bot = TelegramBridgeBot(bot_token, allowed_id)
            bot.start_polling()
            break
        except KeyboardInterrupt:
            break
        except Exception as fatal_err:
            log_activity(f"🚨 Watchdog: Bot mengalami error ({fatal_err}), me-restart otomatis dalam 5 detik...")
            time.sleep(5)
