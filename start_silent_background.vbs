Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\ai-bot"
WshShell.Run "python ""D:\ai-bot\bot.py""", 0, False
Set WshShell = Nothing
