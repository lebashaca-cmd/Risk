@echo off
go build -ldflags "-H=windowsgui -s -w" -o RiskPanel.exe .
if errorlevel 1 (echo Build failed. Is Go installed? https://go.dev/dl/) else (echo Built RiskPanel.exe)
