@echo off
chcp 65001 >nul
title Matikan Auto-Start Bot
cd /d "%~dp0"
python setup_autostart.py --disable
pause
