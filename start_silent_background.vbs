Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\AI BOT"
WshShell.Run "python ""D:\AI BOT\bot.py""", 0, False
Set WshShell = Nothing
