$ErrorActionPreference = 'Stop'
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\runtimes\cua_node'
$node = Get-ChildItem -LiteralPath $runtimeRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName 'bin\node.exe' } | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-Item -LiteralPath $_ } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $node) {
$nodeCommand = Get-Command node -CommandType Application -ErrorAction Stop | Select-Object -First 1
  $node = Get-Item -LiteralPath $nodeCommand.Source
}
$script = Join-Path $PSScriptRoot 'gsd-check-update.js'
& $node.FullName $script
exit $LASTEXITCODE
