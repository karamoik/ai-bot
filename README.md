# 🤖 AI-Bot: Universal AI Agent Telegram Bridge

Jembatan kendali & monitoring 2-arah antara **HP (Telegram)** dan **Semua AI Agent di PC/Laptop Anda** (Google Antigravity, OpenCode, Claude Code, Cursor, Windsurf, Aider, Codex, dll.).

Dibangun menggunakan **100% Python Standard Library** tanpa perlu `pip install` dependensi luar apa pun!

---

## 🌟 Fitur Utama
- 📱 **Interactive Prompt Launchpad:** Kirim prompt dari HP, pilih AI Agent (OpenCode / Antigravity), ganti Model, pilih Folder Project, atau ganti mode keamanan sebelum dijalankan.
- 🎙️ **Voice Note to Prompt (Speech-to-Code):** Cukup rekam pesan suara (*Voice Note*) di Telegram saat sedang di jalan, bot otomatis mengubah suara menjadi teks prompt dan membuka *Launchpad Card*.
- 🔀 **Git Control Center & Visual Diff (`/git`):** Lihat perubahan kode (`git diff`), pindah/buat branch, `git pull`, hingga **1-Tap Quick Commit & Push** langsung dari HP.
- 🌐 **Live Web Preview Tunnel (`/preview`):** Deteksi otomatis port web lokal yang aktif (`80`, `3000`, `5173`, `8000`, dll.) dan buat link **HTTPS Publik Instan** agar web lokal di laptop bisa dicoba langsung dari browser HP!
- 📋 **Smart Task Queue (`/queue`):** Jika AI sedang sibuk mengerjakan sebuah task, prompt baru otomatis masuk ke antrean berurutan agar tidak bentrok mengedit file yang sama.
- ⚡ **Quick Prompt Presets (`/presets`):** Tombol sekali tap untuk perintah standar developer (*Code Review & Bug Hunt*, *Run Tests & Fix Error*, *Refactor & Clean Code*, *Commit Message*, dll.) + bisa tambah preset kustom (`/addpreset`).
- 🚨 **Proactive Watchdog & Remote Power Control (`/power`):**
  - *Low Battery Alert:* Notifikasi otomatis ke HP jika baterai laptop `< 20%` dan charger tidak tercolok.
  - *Stuck Task Detector:* Peringatan otomatis jika proses CLI AI menggantung tanpa output baru.
  - *Remote Power Control:* Kunci layar (*Lock Screen*), matikan monitor, *Sleep*, atau *Hibernate* laptop dari jarak jauh.
- 🗂️ **GUI File Explorer (`/files` atau `/dir`):** Buka struktur folder, unduh file kodingan, atau lihat foto langsung dari chat Telegram seperti aplikasi File Manager.
- 🧠 **Live Thinking & Action Stream:** Menampilkan animasi progres dan proses penalaran AI (*thinking process*) secara real-time via kartu lipat interaktif (`<blockquote expandable>`).
- 📸 **High-DPI Screen Capture (`/ss`):** Ambil tangkapan layar laptop secara jernih langsung ke Telegram.
- 💻 **Laptop Health Monitor (`/sys`):** Cek persentase baterai laptop, status charger AC, beban CPU, RAM, uptime bot, dan sisa ruang harddisk C/D.
- 🛡️ **4 Lapis Sabuk Pengaman:**
  1. *Mode AMAN (Plan/Read-Only)* vs *Mode EDIT (Build/Write)*.
  2. *Folder Whitelist/Blacklist*: Memblokir folder sistem (`C:\Windows`, `C:\Program Files`, root drive `C:\`, `D:\`) dan folder pribadi (`C:\Users\<user>`, `Desktop`, `Documents`, `Downloads`).
  3. *Dangerous Command Gate*: Konfirmasi eksplisit saat prompt mengandung kata destruktif (`hapus`, `rm`, `delete`, `drop`, `truncate`, `reset`).
  4. *1-Tap Undo*: Tombol instan membatalkan perubahan file kodingan via Git Restore.
- ☕ **Anti-Sleep Wake-Lock:** Laptop tetap bekerja memproses kodingan tanpa mati ke mode sleep di tengah proses.
- 🚀 **Windows Auto-Start:** Otomatis berjalan di background (*silent*, tanpa jendela CMD) setiap kali Windows dinyalakan.

---

## 📖 PANDUAN LENGKAP INSTALASI DI LAPTOP BARU (DARI AWAL)

Gunakan panduan langkah demi langkah ini jika Anda ingin menginstal atau memindahkan project ini ke laptop lain via **Flashdisk** atau **Git Clone**.

---

### TAHAP 1: Persiapan di Laptop Baru

1. **Install Python 3 (Wajib Python 3.10 ke atas):**
   - Download installer Python dari situs resmi: [https://www.python.org/downloads/](https://www.python.org/downloads/)
   - ⚠️ **SANGAT PENTING:** Saat jendela instalasi terbuka, **centang kotak "Add python.exe to PATH"** di bagian paling bawah sebelum mengklik *Install Now*.
   - Verifikasi lewat terminal CMD/PowerShell:
     ```powershell
     python --version
     ```
2. **Siapkan AI Agent yang Anda gunakan di laptop baru:**
   - Misalnya **OpenCode CLI**: Pastikan command `opencode` sudah dapat dijalankan di terminal.
   - Atau **Google Antigravity (`agy`)**: Pastikan command `agy` sudah aktif di terminal.

---

### TAHAP 2: Salin File Project ke Laptop Baru

Pilih salah satu metode berikut:

#### Pilihan A: Lewat Flashdisk (USB Drive)
1. Salin seluruh isi folder `ai-bot` dari laptop lama ke flashdisk.
2. Di laptop baru, colokkan flashdisk lalu salin (paste) folder tersebut ke drive tujuan, misalnya di:
   `D:\ai-bot` (atau `C:\ai-bot`).

#### Pilihan B: Lewat Git Clone (GitHub)
1. Buka PowerShell di laptop baru, lalu jalankan:
   ```powershell
   git clone https://github.com/<USERNAME-ANDA>/<NAMA-REPO-ANDA>.git "D:\ai-bot"
   cd "D:\ai-bot"
   ```

---

### TAHAP 3: Membuat Bot Telegram & Mendapatkan Token API

Jika Anda ingin membuat bot Telegram baru (atau belum memiliki bot sama sekali):

1. Buka aplikasi **Telegram** di HP atau desktop Anda.
2. Di kolom pencarian (search), ketik dan buka akun resmi **`@BotFather`** (pastikan yang memiliki centang biru resmi).
3. Klik tombol **Start** atau ketik pesan:
   ```text
   /newbot
   ```
4. `@BotFather` akan meminta **Nama Tampilan** untuk bot Anda. Ketik nama bebas, contoh:
   ```text
   Willy AI Laptop Hub
   ```
5. `@BotFather` akan meminta **Username** untuk bot Anda.
   - Username harus unik (belum pernah dipakai orang lain) dan **wajib diakhiri dengan kata `bot`**.
   - Contoh: `willy_laptop_ai_bot` atau `my_coding_assistant_bot`.
6. Jika berhasil, `@BotFather` akan mengirimkan pesan berisi selamat dan **HTTP API Token** berupa deretan angka & huruf panjang, contohnya:
   ```text
   1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ123456
   ```
7. **Salin (Copy)** token tersebut. Simpan baik-baik dan jangan dibagikan ke orang lain.

---

### TAHAP 4: Menjalankan Installer Otomatis (1x Klik)

1. Buka File Explorer di laptop baru, lalu masuk ke folder project: **`D:\ai-bot`**.
2. Klik 2x (double-click) file:
   👉 **`setup_new_pc.bat`**
3. Jendela terminal hitam akan terbuka dan menjalankan setup:
   - Membuat file `.env` otomatis.
   - Memasang hook notifikasi untuk Google Antigravity, Claude Code, Cursor, Windsurf, dan OpenCode.
   - Mendaftarkan bot ke **Windows Startup** laptop baru (agar otomatis aktif setiap kali laptop dinyalakan).
4. Terminal akan meminta Anda memasukkan token:
   ```text
   👉 Paste Bot Token Anda di sini lalu tekan Enter:
   ```
   **Paste** token yang Anda dapatkan dari `@BotFather` tadi, lalu tekan **Enter**.
5. Terminal akan menampilkan tulisan:
   ```text
   🤖 Bot Telegram Aktif: @nama_bot_anda
   ```
6. **Auto-Pairing Chat ID (Hubungkan ke HP Anda):**
   - Buka aplikasi Telegram di HP Anda.
   - Buka bot baru yang tadi Anda buat, lalu tekan tombol **START** (atau kirim pesan `/start`).
   - Bot akan membalas:
     > *🎉 Berhasil Terhubung! Chat ID Anda otomatis disimpan ke .env.*
   - Akun Telegram Anda sekarang sudah terkunci sebagai pemilik bot, dan bot tidak akan merespons chat dari orang lain.
7. Anda dapat menutup jendela CMD tersebut. Instalasi selesai 100%!

---

### TAHAP 5: Menjalankan Bot Sehari-hari

- **Setelah Restart Laptop:**
  Anda **tidak perlu melakukan apa pun**. Bot otomatis berjalan di background secara senyap (*silent*, tanpa jendela CMD) setiap kali Windows dinyalakan.
- **Jika Ingin Menyalakan Manual Tanpa Restart:**
  Cukup klik 2x file **`start_silent_background.vbs`** di folder `D:\ai-bot`.
- **Jika Ingin Memantau Log Aktivitas di Laptop:**
  Klik 2x file **`monitor_laptop.bat`** untuk melihat lalu-lintas prompt dan jawaban secara live di layar laptop.

---

## 📱 DAFTAR PERINTAH LENGKAP DARI HP (TELEGRAM)

| Perintah | Fungsi |
| :--- | :--- |
| **Kirim pesan biasa** | Membuka *Interactive Prompt Launchpad* untuk konfirmasi eksekusi prompt |
| **Kirim Voice Note 🎙️** | Mengubah pesan suara menjadi teks prompt otomatis (*Speech-to-Code*) |
| **Kirim foto/gambar** | Menganalisis tangkapan layar / foto bug kodingan yang dikirim |
| **`/git`** | Membuka **Git Control Center** (Diff, Quick Commit & Push, Pindah Branch, Pull) |
| **`/preview`** | Membuka **Live Web Preview** (Buat link HTTPS ke web localhost laptop dari HP) |
| **`/presets`** | Membuka daftar **Quick Prompt Presets** (Review, Test, Refactor, dll.) |
| **`/addpreset <Judul> \| <Prompt>`** | Menambahkan template prompt kustom baru ke daftar `/presets` |
| **`/queue`** | Melihat & mengelola **Antrean Prompt Otomatis** (*Smart Task Queue*) |
| **`/power`** | Membuka **Remote Power Control** (Lock Screen, Matikan Layar, Sleep, Hibernate) |
| **`/files`** atau **`/dir`** | Membuka *GUI File Explorer* interaktif untuk jelajah file & download kode |
| **`/models`** | Memilih dan mengganti Model AI yang aktif secara live |
| **`/projects`** | Memilih & berpindah folder project kodingan di laptop (Auto-Scan) |
| **`/ss`** | Mengambil tangkapan layar laptop saat ini (*High-DPI screenshot*) |
| **`/sys`** | Membuka dashboard baterai, CPU, RAM, uptime, dan sisa harddisk laptop |
| **`/mode`** | Ganti mode keamanan: `🟢 AMAN (Plan / Read-Only)` vs `🔴 EDIT (Build / Write)` |
| **`/tasks`** | Melihat daftar AI Agent yang sedang berjalan di laptop |
| **`/kill <id>`** | Menghentikan proses AI Agent yang sedang berjalan |
| **`/new`** | Memulai sesi percakapan/topik baru yang segar |
| **`/cmd <perintah>`** | Menjalankan perintah terminal cepat dari HP (misal: `/cmd git status`) |
| **`/help`** | Membuka Menu Dashboard Utama & panduan navigasi cepat |

---

## 🔒 KEAMANAN & PRIVASI (PUSH KE GITHUB)
File rahasia Anda seperti `.env` (berisi Token Bot & Chat ID pribadi), riwayat log `activity.log`, tangkapan layar `screenshot_*.png`, dan file upload sudah otomatis terdaftar di [`.gitignore`](file:///D:/ai-bot/.gitignore). Anda aman melakukan `git push` ke GitHub publik maupun privat tanpa risiko kebocoran data.
