@echo off
chcp 65001 >nul
title Live Monitor - AI Bot Activity
cd /d "%~dp0"
if not exist activity.log type nul > activity.log
echo ============================================================
echo 👀 LIVE MONITOR AKTIVITAS BOT TELEGRAM DI LAPTOP
echo (Menampilkan semua prompt dan task dari HP secara real-time)
echo ============================================================
echo.
powershell -NoProfile -Command "Get-Content 'D:\AI BOT\activity.log' -Wait -Tail 30 -Encoding UTF8"
