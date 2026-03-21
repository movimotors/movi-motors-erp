# Genera una carpeta dentro de Movi\respaldos\, lista para Google Drive y git init nuevo.
# Ejecutar desde la raiz del proyecto:  powershell -ExecutionPolicy Bypass -File .\empresa_backup_drive\generar_respaldo.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$outRoot = Join-Path $repoRoot "respaldos"
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$destName = "Movi_backup_para_drive_$stamp"
$dest = Join-Path $outRoot $destName

if (-not (Test-Path -LiteralPath $repoRoot)) {
    Write-Error "No se encontro la raiz del repo: $repoRoot"
}

Write-Host "Origen : $repoRoot"
Write-Host "Destino: $dest"
Write-Host ""

if (Test-Path -LiteralPath $dest) {
    Write-Error "Ya existe: $dest"
}

$null = New-Item -ItemType Directory -Path $outRoot -Force
$null = New-Item -ItemType Directory -Path $dest -Force

# Robocopy: copia el arbol; sin .git para repo limpio en destino. Excluye "respaldos" para no meter backups viejos dentro del nuevo paquete.
# Codigos 0-7 = exito en robocopy.
& robocopy.exe "$repoRoot" "$dest" /E `
    /XD .git __pycache__ .venv venv auto_backups node_modules respaldos `
    /XF secrets.toml auth_state.json .DS_Store Thumbs.db `
    /NFL /NDL /NJH /NS /NC /NP
$code = $LASTEXITCODE
if ($code -ge 8) {
    Write-Error "robocopy fallo con codigo $code (revisa permisos y rutas con espacios)"
}

# Copia visible al tope del paquete (instrucciones)
$readmeSrc = Join-Path $PSScriptRoot "INSTRUCCIONES.md"
$readmeDst = Join-Path $dest "00_LEEME_GOOGLE_DRIVE_Y_REPO_NUEVO.md"
Copy-Item -LiteralPath $readmeSrc -Destination $readmeDst -Force

Write-Host ""
Write-Host "Listo. Copia esta carpeta a Google Drive:"
Write-Host "  $dest"
Write-Host ""
