#!/bin/sh
set -e
cd "$(dirname "$0")"
GOOS=windows GOARCH=amd64 go build -ldflags "-H=windowsgui -s -w" -o RiskPanel.exe .
go build -o riskpanel .
echo "Built RiskPanel.exe (Windows) and riskpanel (this computer)."
