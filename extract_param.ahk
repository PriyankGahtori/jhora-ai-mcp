#NoTrayIcon
SetTitleMatchMode, 2

DELAY_KILL        = 2000
DELAY_LAUNCH      = 15000
DELAY_AFTER_WIN   = 3000
DELAY_CHART_COPY  = 15000
DELAY_DIV_MENU1   = 3000
DELAY_DIV_SELECT  = 3000
DELAY_DIV_MENU2   = 3000
DELAY_DIV_COPY    = 10000
DELAY_CLOSE       = 1000

JHD_PATH = %1%

if (JHD_PATH = "") {
    MsgBox, Usage: extract_param.ahk "C:\path\to\chart.jhd"
    ExitApp
}

Process, Close, jhora.exe
Sleep, %DELAY_KILL%

Run, "C:\Program Files (x86)\Jagannatha Hora\bin\jhora.exe" "%JHD_PATH%"
Sleep, %DELAY_LAUNCH%

WinWaitActive, Jagannatha Hora, , 30
Sleep, %DELAY_AFTER_WIN%

WinActivate, Jagannatha Hora
Sleep, 1000
Send, ^c
Sleep, %DELAY_CHART_COPY%

IfWinExist, Copied
{
    ControlClick, Button1, Copied
    Sleep, 500
}

IfExist, C:\windows\temp\chart_data.txt
    FileDelete, C:\windows\temp\chart_data.txt
FileAppend, %Clipboard%, C:\windows\temp\chart_data.txt

WinActivate, Jagannatha Hora
Sleep, 1000
Send, +{F10}
Sleep, %DELAY_DIV_MENU1%
Send, a
Sleep, %DELAY_DIV_SELECT%

WinActivate, Jagannatha Hora
Sleep, 500
Send, +{F10}
Sleep, %DELAY_DIV_MENU2%
Send, {Up}
Sleep, 500
Send, {Enter}
Sleep, %DELAY_DIV_COPY%

IfWinExist, Copied
{
    ControlClick, Button1, Copied
    Sleep, 500
}

IfExist, C:\windows\temp\divisionals.txt
    FileDelete, C:\windows\temp\divisionals.txt
FileAppend, %Clipboard%, C:\windows\temp\divisionals.txt

WinClose, Jagannatha Hora
Sleep, %DELAY_CLOSE%
IfWinExist, Jagannatha Hora
    WinClose, Jagannatha Hora

ExitApp
