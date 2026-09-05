# One-command end-to-end demo (Windows PowerShell).
# Boots all 3 services, seeds, and runs the agent happy path + extras.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (Test-Path "venv/Scripts/python.exe") {
    $py = "venv/Scripts/python.exe"
} else {
    $py = "python"
}

& $py -m scripts.run_demo
