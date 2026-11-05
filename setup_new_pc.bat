@echo off
chcp 65001 >nul
title Installer Otomatis ai-bot untuk Laptop Baru
cd /d "%~dp0"

echo =================================================================
echo 🤖 SETUP OTOMATIS ai-bot UNTUK LAPTOP BARU
echo =================================================================
echo.

:: 1. Cek instalasi Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ERROR: Python belum terinstal di laptop ini atau belum masuk ke PATH!
    echo Silakan install Python 3.10+ terlebih dahulu dari python.org.
    echo (Pastikan centang "Add python.exe to PATH" saat install).
    echo.
    pause
    exit /b 1
)

echo ✅ Python terdeteksi.

:: 2. Siapkan file .env jika belum ada
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo ✅ File .env berhasil dibuat dari template.
    ) else (
        echo TELEGRAM_BOT_TOKEN=> .env
        echo TELEGRAM_CHAT_ID=> .env
        echo DEFAULT_WORKSPACE=C:\Users\%USERNAME%>> .env
    )
)

:: 3. Pasang Notifikasi Otomatis untuk AI Agent yang ada di laptop ini
echo.
echo [1/3] Memasang hook notifikasi untuk AI Agent di PC...
python setup_hooks.py

:: 4. Pasang Auto-Start Windows Startup
echo.
echo [2/3] Mendaftarkan ai-bot ke Windows Startup (Auto-Start saat PC nyala)...
python setup_autostart.py

:: 5. Menjalankan Bot untuk Pertama Kali (Auto-Pairing)
echo.
echo =================================================================
echo [3/3] MENJALANKAN BOT UNTUK SETUP PERTAMA KALI
echo =================================================================
echo.
echo Petunjuk:
echo 1. Jika diminta masukkan Bot Token, paste Token dari @BotFather lalu Enter.
echo 2. Buka bot di Telegram HP Anda lalu kirim pesan /start.
echo 3. Chat ID Anda akan otomatis tersimpan (Auto-Pairing)!
echo =================================================================
echo.
python bot.py
pause
