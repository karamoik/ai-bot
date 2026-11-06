Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\ai-bot"
WshShell.Run """D:\free_project\laragon\bin\python\python-3.13\python.exe"" ""D:\ai-bot\bot.py""", 0, False
Set WshShell = Nothing
