@echo off
chcp 65001 >nul
title Setup Auto Notification Hooks
cd /d "%~dp0"
python setup_hooks.py
echo.
echo Selesai! Sekarang semua AI Agent Anda akan otomatis mengirim notifikasi ke Telegram setiap selesai mengerjakan prompt.
pause
