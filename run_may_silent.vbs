Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = currentDir & "\.venv\Scripts\pythonw.exe"
scriptPath = currentDir & "\may_assistant.py"

If Not fso.FileExists(pythonwPath) Then
    MsgBox "MAY's Python runtime was not found: " & pythonwPath, vbExclamation, "MAY"
    WScript.Quit 1
End If
If Not fso.FileExists(scriptPath) Then
    MsgBox "MAY's program was not found: " & scriptPath, vbExclamation, "MAY"
    WScript.Quit 1
End If

WshShell.CurrentDirectory = currentDir
args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " """ & WScript.Arguments(i) & """"
Next

WshShell.Run """" & pythonwPath & """ """ & scriptPath & """" & args, 0, False