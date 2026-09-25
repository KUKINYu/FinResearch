Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = "F:\于劭然\Fintech"
If Not fso.FolderExists(base) Then
  MsgBox "找不到 FinResearch 项目目录：" & base, 48, "FinResearch"
  WScript.Quit 1
End If
WshShell.CurrentDirectory = base
WshShell.Run "cmd /c " & base & "\scripts\launch.bat", 0, False
