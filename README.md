# 🤖 Universal AI Agent Telegram Hub (`D:\AI BOT`)

Sistem jembatan 2-arah antara **HP (Telegram)** dan **Semua AI Agent di PC Anda** (Google Antigravity, Claude Code, Cursor, Windsurf, Aider, Codex, dll.).
Dibuat menggunakan **100% Python Standard Library** (tanpa perlu `pip install` library tambahan!).

---

## 🚀 Langkah 1: Cara Membuat Bot Token Telegram (1 Menit)

Karena Anda belum memiliki Bot Token, ikuti langkah mudah berikut di HP Anda:

1. Buka aplikasi **Telegram** dan cari akun resmi **`@BotFather`** (ada centang biru).
2. Ketik dan kirim pesan: **`/newbot`**
3. `@BotFather` akan meminta **nama tampilan** bot Anda. Ketik bebas, misalnya:
   `Willy AI Agent Hub`
4. `@BotFather` akan meminta **username** bot (harus unik dan diakhiri kata `bot`). Misalnya:
   `willy_ai_agent_bot`
5. Selesai! `@BotFather` akan memberikan **HTTP API Token** (contoh: `7123456789:AAHxyz...`). Salin token tersebut.

---

## ⚡ Langkah 2: Menjalankan Bot & Auto-Pairing Chat ID

1. Buka folder `D:\AI BOT` lalu klik 2x file **`start_bot.bat`** (atau jalankan `python "D:\AI BOT\bot.py"` di terminal).
2. Saat pertama kali dijalankan, jendela terminal akan meminta Anda melakukan **Paste Bot Token** dari `@BotFather`. Paste token tersebut lalu tekan **Enter** (otomatis tersimpan ke [`.env`](file:///D:/AI%20BOT/.env)).
3. Buka bot baru Anda di Telegram HP, lalu tekan **Start** (atau kirim `/start`).
4. **Auto-Pairing:** Bot akan langsung mengenali akun Telegram Anda, menyimpan `TELEGRAM_CHAT_ID` Anda secara otomatis ke file [`.env`](file:///D:/AI%20BOT/.env), dan mengunci akses agar **hanya HP Anda** yang bisa memberi perintah ke PC.

---

## 🔔 Langkah 3: Mengaktifkan Notifikasi Otomatis dari Semua AI Agent

### A. Untuk Google Antigravity & Claude Code (Otomatis 100% via Lifecycle Hook)
Klik 2x file **`enable_auto_notify.bat`** (atau jalankan `python "D:\AI BOT\setup_hooks.py"`).
Script ini akan mendaftarkan `Stop` hook ke:
- `~/.gemini/config/hooks.json` (untuk **Google Antigravity**)
- `~/.claude/settings.json` (untuk **Claude Code**)

Setiap kali prompt selesai dikerjakan di IDE/CLI, Anda akan langsung mendapat pesan Telegram berisi nama workspace, prompt terakhir, dan ringkasan jawaban AI!

*(Untuk mematikan hook otomatis kapan saja, jalankan: `python "D:\AI BOT\setup_hooks.py" --disable`)*

### B. Untuk Cursor, Windsurf, VS Code Copilot (Via MCP Server)
Tambahkan konfigurasi berikut ke pengaturan **MCP Servers** di Cursor / Windsurf / IDE Anda:

```json
{
  "mcpServers": {
    "telegram-notifier": {
      "command": "python",
      "args": ["D:\\AI BOT\\mcp_server.py"]
    }
  }
}
```
Dengan MCP ini, AI Agent mana pun memiliki tool `send_telegram_notification` untuk mengabari Anda di HP begitu selesai mengerjakan tugas.

### C. Untuk Terminal / Script Custom Apa Saja (CLI Wrapper)
Gunakan [`notify.py`](file:///D:/AI%20BOT/notify.py) untuk membungkus perintah apa pun agar mengirim notifikasi saat selesai:
```powershell
python "D:\AI BOT\notify.py" --agent "Build/Test" --run npm run build
```
Atau kirim pesan langsung:
```powershell
python "D:\AI BOT\notify.py" --agent "CustomAgent" -m "Proses training selesai!"
```

---

## 📱 Daftar Perintah dari HP (Telegram)

Saat `start_bot.bat` (`bot.py`) berjalan di PC:
- **Ketik pesan biasa (tanpa `/`)**: Langsung melempar prompt tersebut ke AI Agent yang sedang aktif di folder workspace aktif!
- `/ask <agent> <prompt>`: Melempar prompt ke AI agent tertentu (contoh: `/ask agy buatkan unit test untuk utils.py` atau `/ask claude review perubahan git terakhir`).
- `/agents`: Melihat daftar AI Agent yang terdaftar di [`config.json`](file:///D:/AI%20BOT/config.json).
- `/agent <kode>`: Mengganti AI Agent default (`agy`, `claude`, `aider`, `codex`, `gemini`).
- `/mode <build|plan>`: Mengganti mode OpenCode dari HP (`plan` = read-only, hanya analisis & rencana; `build` = boleh edit file). Bisa juga langsung kirim prompt: `/mode plan <prompt>`.
- `/projects`: Melihat daftar shortcut folder project.
- `/cd <shortcut_atau_path>`: Berpindah folder project kerja dari HP (contoh: `/cd D:\ProjectKu`).
- `/addproject <nama> <path>`: Menyimpan shortcut folder baru dari HP (contoh: `/addproject toko D:\Projects\toko-online`).
- `/tasks`: Melihat daftar AI Agent yang sedang bekerja di background.
- `/kill <nomor_task>`: Menghentikan proses AI Agent yang sedang berjalan dari HP.
- `/cmd <perintah>`: Menjalankan perintah terminal cepat dari HP (contoh: `/cmd git status`).
