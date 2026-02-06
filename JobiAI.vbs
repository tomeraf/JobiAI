' JobiAI Silent Launcher
' Starts backend and frontend completely hidden with SQLite database
' Double-click to run - auto-exits when browser tab closes
' Manual stop: run exit-JobiAI.bat

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get script directory
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
backendDir = scriptDir & "\backend"
frontendDir = scriptDir & "\frontend"
envFile = backendDir & "\.env"
envBackup = backendDir & "\.env.dev"

' Temporarily rename .env to prevent it from overriding our SQLite setting
If fso.FileExists(envFile) Then
    If fso.FileExists(envBackup) Then
        fso.DeleteFile(envBackup)
    End If
    fso.MoveFile envFile, envBackup
End If

' Set data directory
dataDir = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\JobiAI"
If Not fso.FolderExists(dataDir) Then
    fso.CreateFolder(dataDir)
End If

' Database URL for SQLite - use forward slashes for SQLAlchemy URL
dbPath = Replace(dataDir, "\", "/") & "/jobiai.db"
dbUrl = "sqlite+aiosqlite:///" & dbPath

' Start backend (completely hidden, 0 = hide window)
backendCmd = "cmd /c cd /d """ & backendDir & """ && set ""DATABASE_URL=" & dbUrl & """ && python -m uvicorn app.main:app --host 127.0.0.1 --port 9000 --log-level warning"
WshShell.Run backendCmd, 0, False

' Wait for backend
WScript.Sleep 3000

' Restore .env file
If fso.FileExists(envBackup) Then
    If fso.FileExists(envFile) Then
        fso.DeleteFile(envFile)
    End If
    fso.MoveFile envBackup, envFile
End If

' Start frontend (completely hidden)
frontendCmd = "cmd /c cd /d """ & frontendDir & """ && npm run dev -- --port 5173"
WshShell.Run frontendCmd, 0, False

' Wait for frontend
WScript.Sleep 3000

' Open browser
WshShell.Run "http://localhost:5173", 1, False

' Show confirmation
MsgBox "JobiAI started!" & vbCrLf & vbCrLf & _
       "Backend: http://localhost:9000" & vbCrLf & _
       "Frontend: http://localhost:5173" & vbCrLf & _
       "Database: " & dbUrl & vbCrLf & vbCrLf & _
       "Close the browser tab to stop JobiAI." & vbCrLf & _
       "Or run exit-JobiAI.bat to force stop.", vbInformation, "JobiAI"
