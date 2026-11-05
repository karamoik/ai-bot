@echo off
chcp 65001 >nul
title Universal AI Agent Telegram Bridge
cd /d "%~dp0"
python bot.py
pause
