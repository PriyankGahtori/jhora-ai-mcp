#NoTrayIcon
SetTitleMatchMode, 2

; ── Timing configuration ─────────────────────────────────────────────────────
; Adjust these values based on your machine's performance.
; Increase if JHora doesn't load in time or clipboard copy fails.
; Decrease if your machine is fast and you want shorter run time.

DELAY_KILL        = 2000   ; Wait after killing existing jhora.exe
DELAY_LAUNCH      = 5000   ; Wait for JHora to fully load after launch (increase on slow machines: 10000-18000)
DELAY_AFTER_WIN   = 2000   ; Extra settle time after WinWaitActive
DELAY_CHART_COPY  = 6000   ; Wait for Ctrl+C chart data copy (increase on slow machines: 10000-15000)
DELAY_DIV_MENU1   = 1500   ; Wait for first context menu to open
DELAY_DIV_SELECT  = 2000   ; Wait after pressing 'a' to select divisional option
DELAY_DIV_MENU2   = 1500   ; Wait for second context menu to open
DELAY_DIV_COPY    = 2000   ; Wait for divisional data copy (increase on slow machines: 8000-10000)
DELAY_CLOSE       = 1000   ; Wait after WinClose

; ─────────────────────────────────────────────────────────────────────────────

; Arg: %1% = full Windows path to JHD file (e.g. C:\windows\temp\input.jhd)
JHD_PATH = %1%

if (JHD_PATH = "") {
    MsgBox, Usage: extract_param.ahk "C:\path\to\chart.jhd"
    ExitApp
}

; Kill existing JHora
Process, Close, jhora.exe
Sleep, %DELAY_KILL%

; Launch with the given JHD
Run, "C:\Program Files (x86)\Jagannatha Hora\bin\jhora.exe" "%JHD_PATH%"
Sleep, %DELAY_LAUNCH%

WinWaitActive, Jagannatha Hora, , 30
Sleep, %DELAY_AFTER_WIN%

; ── Step 1: All Divisional Longitudes (Shift+F10 → A) — DISABLED ─────────────
; Send, +{F10}
; Sleep, 2500
; Send, a
; Sleep, 5000
; IfWinExist, Copied
; {
;     ControlClick, Button1, Copied
;     Sleep, 500
; }
; IfExist, C:\windows\temp\divisionals.txt
;     FileDelete, C:\windows\temp\divisionals.txt
; FileAppend, %Clipboard%, C:\windows\temp\divisionals.txt

; ── Step 2: Full chart data (Ctrl+C) ─────────────────────────────────────────
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

; ── Step 3: Shadbala component breakup ─────────────────────────────────────
; Open Strengths -> Other strengths, then select Shadbala breakup.
; These are Wine logical screen coordinates measured with Window Spy after
; accounting for the Retina-scaled macOS screenshot.
WinActivate, Jagannatha Hora
WinMaximize, Jagannatha Hora
Sleep, 1000
Click, 185, 88
Sleep, 6000
Click, 560, 839
Sleep, 2000
Click, 1100, 165, Right
Sleep, 500
Send, b
Sleep, 2500
WinActivate, Jagannatha Hora
Sleep, 500
Clipboard :=
; Reopen the table context menu. Up wraps to the final Copy to clipboard
; item because the menu opens with the current breakup item focused.
Click, 1100, 165, Right
Sleep, 500
Send, {Up}
Sleep, 300
Send, {Enter}
ClipWait, 15
clipOK := !ErrorLevel

IfWinExist, Copied
{
    ControlClick, Button1, Copied
    Sleep, 500
}

if (clipOK)
{
    IfExist, C:\windows\temp\shadbala_breakup.txt
        FileDelete, C:\windows\temp\shadbala_breakup.txt
    FileAppend, %Clipboard%, C:\windows\temp\shadbala_breakup.txt
}
Clipboard :=

; ── Step 3b: Kaala Bala per-sub breakup ───────────────────────────────────
GrabBreakup("k", "C:\windows\temp\kaala_breakup.txt")

; ── Step 3c: Sthana Bala per-sub breakup ─────────────────────────────────
; right-click → 't' selects "Sthana Bala" breakup
; (Uchcha / Saptavargaja / Oja Yugma / Kendra / Drekkana).
; ('c'/'r' give only single-column Cheshta/Drig totals — no sub-breakup.)
GrabBreakup("t", "C:\windows\temp\sthana_breakup.txt")

; ── Step 4: Divisional chart data (context menu → a → context menu → Up → Enter) ──
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

; Close JHora
WinClose, Jagannatha Hora
Sleep, %DELAY_CLOSE%
IfWinExist, Jagannatha Hora
    WinClose, Jagannatha Hora

ExitApp

; ── Helper: select a Strengths-table breakup by accelerator letter and copy ──
GrabBreakup(letter, outFile)
{
    WinActivate, Jagannatha Hora
    Sleep, 1000
    Click, 1100, 165, Right
    Sleep, 500
    Send, %letter%
    Sleep, 2500
    WinActivate, Jagannatha Hora
    Sleep, 500
    Clipboard :=
    Click, 1100, 165, Right
    Sleep, 500
    Send, {Up}
    Sleep, 300
    Send, {Enter}
    ClipWait, 15
    ok := !ErrorLevel
    IfWinExist, Copied
    {
        ControlClick, Button1, Copied
        Sleep, 500
    }
    if (ok)
    {
        IfExist, %outFile%
            FileDelete, %outFile%
        FileAppend, %Clipboard%, %outFile%
    }
    Clipboard :=
}
