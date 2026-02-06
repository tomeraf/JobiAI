' JobiAI Launcher
' Starts backend with built-in frontend
' Double-click to run - auto-exits when browser tab closes

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get script directory
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
backendDir = scriptDir & "\backend"

' Set data directory
dataDir = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\JobiAI"
If Not fso.FolderExists(dataDir) Then
    fso.CreateFolder(dataDir)
End If

' Database URL for SQLite - use forward slashes for SQLAlchemy URL
dbPath = Replace(dataDir, "\", "/") & "/jobiai.db"
dbUrl = "sqlite+aiosqlite:///" & dbPath

' Check if venv exists
If Not fso.FolderExists(backendDir & "\venv") Then
    MsgBox "Python environment not found!" & vbCrLf & vbCrLf & _
           "Please run install.bat first.", vbCritical, "JobiAI"
    WScript.Quit
End If

' Start backend with venv Python (completely hidden, 0 = hide window)
backendCmd = "cmd /c cd /d """ & backendDir & """ && set ""DATABASE_URL=" & dbUrl & """ && venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 9000 --log-level warning"
WshShell.Run backendCmd, 0, False

' Wait for backend to start
WScript.Sleep 4000

' Open browser to the app
WshShell.Run "http://localhost:9000", 1, False

' Show confirmation
MsgBox "JobiAI started!" & vbCrLf & vbCrLf & _
       "App: http://localhost:9000" & vbCrLf & _
       "Database: " & dbUrl & vbCrLf & vbCrLf & _
       "Close the browser tab to stop JobiAI." & vbCrLf & _
       "Or run exit-JobiAI.bat to force stop.", vbInformation, "JobiAI"
