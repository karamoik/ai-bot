@echo off
chcp 65001 >nul
title Aktifkan Auto-Start Bot Saat Laptop Menyala
cd /d "%~dp0"
python setup_autostart.py
pause
