# 🤖 Universal AI Agent Telegram Hub (`D:\ai-bot`)

Sistem jembatan 2-arah antara **HP (Telegram)** dan **Semua AI Agent di PC Anda** (Google Antigravity, OpenCode, Claude Code, Cursor, Windsurf, Aider, Codex, dll.).
Dibuat menggunakan **100% Python Standard Library** (tanpa perlu `pip install` library tambahan!).

---

## 🚀 Langkah 1: Cara Membuat Bot Token Telegram (1 Menit)

Jika belum memiliki Bot Token, ikuti langkah mudah berikut di HP Anda:

1. Buka aplikasi **Telegram** dan cari akun resmi **`@BotFather`** (ada centang biru).
2. Ketik dan kirim pesan: **`/newbot`**
3. `@BotFather` akan meminta **nama tampilan** bot Anda. Ketik bebas, misalnya:
   `Willy AI Agent Hub`
4. `@BotFather` akan meminta **username** bot (harus unik dan diakhiri kata `bot`). Misalnya:
   `willy_ai_agent_bot`
5. Selesai! `@BotFather` akan memberikan **HTTP API Token** (contoh: `7123456789:AAHxyz...`). Salin token tersebut.

---

## ⚡ Langkah 2: Menjalankan Bot & Auto-Pairing Chat ID

1. Buka folder `D:\ai-bot` lalu klik 2x file **`start_silent_background.vbs`** (atau jalankan `start_bot.bat` untuk melihat jendela terminal).
2. Saat pertama kali dijalankan, jika file `.env` belum ada, jalankan lewat `start_bot.bat` dan paste token dari `@BotFather` lalu tekan **Enter** (otomatis tersimpan ke `.env`).
3. Buka bot baru Anda di Telegram HP, lalu tekan **Start** (atau kirim `/start`).
4. **Auto-Pairing:** Bot akan langsung mengenali akun Telegram Anda, menyimpan `TELEGRAM_CHAT_ID` Anda secara otomatis ke file `.env`, dan mengunci akses agar **hanya HP Anda** yang bisa memberi perintah ke PC.

---

## 🔔 Langkah 3: Mengaktifkan Notifikasi Otomatis dari Semua AI Agent

### A. Untuk Google Antigravity & Claude Code (Otomatis 100% via Lifecycle Hook)
Klik 2x file **`enable_auto_notify.bat`** (atau jalankan `python "D:\ai-bot\setup_hooks.py"`).
Script ini akan mendaftarkan `Stop` hook ke:
- `~/.gemini/config/hooks.json` (untuk **Google Antigravity**)
- `~/.claude/settings.json` (untuk **Claude Code**)

Setiap kali prompt selesai dikerjakan di IDE/CLI, Anda akan langsung mendapat pesan Telegram berisi nama workspace, prompt terakhir, dan ringkasan jawaban AI!

*(Untuk mematikan hook otomatis kapan saja, jalankan: `python "D:\ai-bot\setup_hooks.py" --disable`)*

### B. Untuk Cursor, Windsurf, VS Code Copilot (Via MCP Server)
Konfigurasi MCP Server di Cursor / Windsurf (`~/.cursor/mcp.json` / `~/.codeium/windsurf/mcp_config.json`):

```json
{
  "mcpServers": {
    "telegram-notifier": {
      "command": "python",
      "args": ["D:\\ai-bot\\mcp_server.py"]
    }
  }
}
```
Dengan MCP ini, AI Agent mana pun memiliki tool `send_telegram_notification` untuk mengabari Anda di HP begitu selesai mengerjakan tugas.

### C. Untuk Terminal / Script Custom Apa Saja (CLI Wrapper)
Gunakan `notify.py` untuk membungkus perintah apa pun agar mengirim notifikasi saat selesai:
```powershell
python "D:\ai-bot\notify.py" --agent "Build/Test" --run npm run build
```
Atau kirim pesan langsung:
```powershell
python "D:\ai-bot\notify.py" --agent "CustomAgent" -m "Proses training selesai!"
```

---

## 📱 Fitur & Menu Dashboard dari HP (Telegram)

Saat bot berjalan di laptop:
- **Ketik pesan biasa / kirim foto**: Membuka **Interactive Prompt Launchpad** untuk memilih Agent (OpenCode, Antigravity, dll.), ganti model, ganti project, atau switch mode sebelum dieksekusi.
- **`/files` atau `/dir`**: Membuka **GUI File Explorer** untuk melihat isi folder kerja, download file kodingan, atau melihat foto langsung di Telegram.
- **`/models`**: Membuka menu interaktif untuk mengganti Model AI secara live.
- **`/projects`**: Menampilkan daftar shortcut folder project hasil auto-scan (`D:\free_project`, `laragon\www`, dll.).
- **`/ss`**: Mengambil tangkapan layar laptop secara jernih (High-DPI).
- **`/sys`**: Membuka dashboard kesehatan laptop (Baterai, RAM, CPU, Uptime, Sisa Harddisk).
- **`/mode`**: Mengganti mode keamanan `🟢 AMAN (Plan / Read-Only)` vs `🔴 EDIT (Build / Write)`.
- **`/tasks` & `/kill <id>`**: Memantau dan menghentikan AI Agent yang sedang bekerja di laptop.
- **`/new`**: Memulai sesi percakapan baru.
- **`/cmd <perintah>`**: Menjalankan perintah terminal cepat dari HP.
