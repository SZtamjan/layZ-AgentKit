# Run in Windows PowerShell STA. Restore the complete clipboard in finally.
param([Parameter(Mandatory=$true)][string]$Blender)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$agentKitRepo = Split-Path -Parent $PSScriptRoot
$agentKitClipboardOriginal = [System.Windows.Forms.Clipboard]::GetDataObject()
$agentKitClipboardBackup = $null
if ($null -ne $agentKitClipboardOriginal) {
    $agentKitClipboardBackup = New-Object System.Windows.Forms.DataObject
    foreach ($agentKitFormat in $agentKitClipboardOriginal.GetFormats($false)) {
        $agentKitClipboardBackup.SetData($agentKitFormat, $false, $agentKitClipboardOriginal.GetData($agentKitFormat, $false))
    }
}
$agentKitBitmap = New-Object System.Drawing.Bitmap 48,32
$agentKitGraphics = [System.Drawing.Graphics]::FromImage($agentKitBitmap)
try {
    $agentKitGraphics.Clear([System.Drawing.Color]::CornflowerBlue)
    [System.Windows.Forms.Clipboard]::SetImage($agentKitBitmap)
    & $Blender --background --factory-startup --threads 2 --python-exit-code 1 --python (Join-Path $PSScriptRoot 'clipboard.py')
    if ($LASTEXITCODE -ne 0) { throw 'Blender clipboard test failed' }
} finally {
    if ($null -ne $agentKitClipboardBackup) {
        [System.Windows.Forms.Clipboard]::SetDataObject($agentKitClipboardBackup, $true)
    } else {
        [System.Windows.Forms.Clipboard]::Clear()
    }
    $agentKitGraphics.Dispose()
    $agentKitBitmap.Dispose()
}
