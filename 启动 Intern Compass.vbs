Option Explicit

Dim fso, shell
Dim rootDir, appDir, scriptPath, logDir, logPath
Dim bundledPythonw, bundledPython, pythonExe, command

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

rootDir = fso.GetParentFolderName(WScript.ScriptFullName)
appDir = fso.BuildPath(rootDir, "intern_compass")
scriptPath = fso.BuildPath(appDir, "main.pyw")
logDir = fso.BuildPath(appDir, "logs")
logPath = fso.BuildPath(logDir, "app_error.log")

If Not fso.FolderExists(logDir) Then
    fso.CreateFolder(logDir)
End If

If Not fso.FileExists(scriptPath) Then
    WriteLog "main.pyw was not found: " & scriptPath
    MsgBox "Intern Compass startup file is missing. See log:" & vbCrLf & logPath, vbCritical, "Intern Compass"
    WScript.Quit 1
End If

bundledPythonw = "C:\Users\Loy\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
bundledPython = "C:\Users\Loy\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

If fso.FileExists(bundledPythonw) Then
    pythonExe = bundledPythonw
ElseIf fso.FileExists(bundledPython) Then
    pythonExe = bundledPython
Else
    pythonExe = "pyw.exe"
End If

shell.CurrentDirectory = appDir
command = """" & pythonExe & """ """ & scriptPath & """"

On Error Resume Next
shell.Run command, 0, False
If Err.Number <> 0 Then
    Err.Clear
    command = "pythonw.exe """ & scriptPath & """"
    shell.Run command, 0, False
End If

If Err.Number <> 0 Then
    WriteLog "Failed to start with pythonw/pyw. Error " & Err.Number & ": " & Err.Description
    MsgBox "Intern Compass failed to start. See log:" & vbCrLf & logPath, vbCritical, "Intern Compass"
    WScript.Quit 1
End If

Sub WriteLog(message)
    Dim file
    Set file = fso.OpenTextFile(logPath, 8, True, -1)
    file.WriteLine "==== Intern Compass launcher error ===="
    file.WriteLine "Time: " & Now
    file.WriteLine message
    file.Close
End Sub
