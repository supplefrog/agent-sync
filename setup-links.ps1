#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$IncludeCodex
)

$ErrorActionPreference = 'Stop'

$repoRoot = $PSScriptRoot
$skillsTarget = Join-Path $repoRoot 'skills'
$agentsMdTarget = Join-Path $repoRoot 'AGENTS.md'
$neonOverride = Join-Path $repoRoot 'overrides\neon.md'
$codexOverride = Join-Path $repoRoot 'overrides\codex.md'

if (-not (Test-Path -LiteralPath $skillsTarget -PathType Container)) {
    throw "Missing skills directory at $skillsTarget"
}
if (-not (Test-Path -LiteralPath $agentsMdTarget -PathType Leaf)) {
    throw "Missing AGENTS.md at $agentsMdTarget"
}

Add-Type -AssemblyName Microsoft.VisualBasic

function Move-ToRecycleBin {
    param([Parameter(Mandatory = $true)][string]$Path, [switch]$IsDirectory)
    if ($IsDirectory) {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
            $Path,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
        )
    } else {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
            $Path,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
        )
    }
}

function Ensure-DirectoryJunction {
    param(
        [Parameter(Mandatory = $true)][string]$LinkPath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    $parentDir = Split-Path -Path $LinkPath -Parent
    if (-not (Test-Path -LiteralPath $parentDir -PathType Container)) {
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
    }

    $normalizedTarget = [System.IO.Path]::GetFullPath($TargetPath).TrimEnd('\')

    if (Test-Path -LiteralPath $LinkPath) {
        $item = Get-Item -LiteralPath $LinkPath -Force
        $isReparse = ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
        if ($isReparse) {
            $currentTarget = $null
            if ($item.Target) {
                $firstTarget = @($item.Target)[0]
                if ($firstTarget) {
                    $currentTarget = [System.IO.Path]::GetFullPath($firstTarget).TrimEnd('\')
                }
            }
            if ($currentTarget -eq $normalizedTarget) {
                Write-Host "OK junction: $LinkPath -> $normalizedTarget"
                return
            }
            [System.IO.Directory]::Delete($LinkPath, $false)
        } else {
            Write-Host "Recycling existing directory: $LinkPath"
            Move-ToRecycleBin -Path $LinkPath -IsDirectory
        }
    }

    $out = cmd /c mklink /J "`"$LinkPath`"" "`"$normalizedTarget`"" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create junction $LinkPath -> $normalizedTarget`: $out"
    }
    Write-Host "Created junction: $LinkPath -> $normalizedTarget"
}

function Ensure-FileHardlink {
    param(
        [Parameter(Mandatory = $true)][string]$LinkPath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    $parentDir = Split-Path -Path $LinkPath -Parent
    if (-not (Test-Path -LiteralPath $parentDir -PathType Container)) {
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
    }

    $normalizedLink = [System.IO.Path]::GetFullPath($LinkPath)
    $normalizedTarget = [System.IO.Path]::GetFullPath($TargetPath)

    if (Test-Path -LiteralPath $normalizedLink) {
        $siblings = & fsutil hardlink list $normalizedTarget 2>$null
        $linkRelative = $normalizedLink.Substring([System.IO.Path]::GetPathRoot($normalizedLink).Length - 1)
        $alreadyLinked = $false
        foreach ($line in $siblings) {
            if ($line.Trim().Equals($linkRelative, [System.StringComparison]::OrdinalIgnoreCase)) {
                $alreadyLinked = $true
                break
            }
        }
        if ($alreadyLinked) {
            Write-Host "OK hardlink: $normalizedLink -> $normalizedTarget"
            return
        }
        Write-Host "Recycling existing file: $normalizedLink"
        Move-ToRecycleBin -Path $normalizedLink
    }

    $out = cmd /c mklink /H "`"$normalizedLink`"" "`"$normalizedTarget`"" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create hardlink $normalizedLink -> $normalizedTarget`: $out"
    }
    Write-Host "Created hardlink: $normalizedLink -> $normalizedTarget"
}

function Write-ComposedFile {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string[]]$SourcePaths,
        [Parameter(Mandatory = $true)][string]$HeaderComment
    )

    $parentDir = Split-Path -Path $TargetPath -Parent
    if (-not (Test-Path -LiteralPath $parentDir -PathType Container)) {
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
    }

    $parts = @($HeaderComment)
    foreach ($src in $SourcePaths) {
        if (Test-Path -LiteralPath $src -PathType Leaf) {
            $parts += [System.IO.File]::ReadAllText($src, [System.Text.Encoding]::UTF8).Trim()
        }
    }
    $content = ($parts -join "`r`n`r`n") + "`r`n"

    # Always remove an existing file/hardlink before writing so source hardlinks are never overwritten.
    if (Test-Path -LiteralPath $TargetPath) {
        Remove-Item -LiteralPath $TargetPath -Force
    }
    [System.IO.File]::WriteAllText($TargetPath, $content, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Composed: $TargetPath"
}

Ensure-DirectoryJunction -LinkPath (Join-Path $HOME '.agents\skills') -TargetPath $skillsTarget
Ensure-DirectoryJunction -LinkPath (Join-Path $HOME '.gemini\config\skills') -TargetPath $skillsTarget

$neonHeader = '<!-- Composed by agent-sync/setup-links.ps1 from AGENTS.md + overrides/neon.md; edit source files in agent-sync. -->'
$neonSources = @($agentsMdTarget, $neonOverride)
$writtenRuleFiles = @()

$geminiAgentsMd = Join-Path $HOME '.gemini\config\AGENTS.md'
Write-ComposedFile -TargetPath $geminiAgentsMd -SourcePaths $neonSources -HeaderComment $neonHeader
$writtenRuleFiles += $geminiAgentsMd

$t3AgyRoot = Join-Path $HOME '.t3\userdata\providers\antigravity'
if (Test-Path -LiteralPath $t3AgyRoot -PathType Container) {
    Get-ChildItem -LiteralPath $t3AgyRoot -Directory | ForEach-Object {
        $cfgDir = Join-Path $_.FullName 'config'
        if (Test-Path -LiteralPath $cfgDir -PathType Container) {
            $t3AgentsMd = Join-Path $cfgDir 'AGENTS.md'
            Write-ComposedFile -TargetPath $t3AgentsMd -SourcePaths $neonSources -HeaderComment $neonHeader
            $writtenRuleFiles += $t3AgentsMd
        }
    }
}

if ($IncludeCodex) {
    $codexHeader = '<!-- Composed by agent-sync/setup-links.ps1 from AGENTS.md + overrides/codex.md; edit source files in agent-sync. -->'
    $codexAgentsMd = Join-Path $HOME '.codex\AGENTS.md'
    Write-ComposedFile -TargetPath $codexAgentsMd -SourcePaths @($agentsMdTarget, $codexOverride) -HeaderComment $codexHeader
    $writtenRuleFiles += $codexAgentsMd
}

Write-Host ""
Write-Host "Verified links:"
Get-Item -LiteralPath (Join-Path $HOME '.agents\skills'), (Join-Path $HOME '.gemini\config\skills') |
    Select-Object FullName, LinkType, Target |
    Format-Table -AutoSize

Write-Host "Composed instruction files:"
Get-Item -LiteralPath $writtenRuleFiles |
    Select-Object FullName, Length, LastWriteTime |
    Format-Table -AutoSize

Write-Host "Discovered skills:"
Get-ChildItem -LiteralPath (Join-Path $HOME '.agents\skills') -Directory |
    Select-Object -ExpandProperty Name |
    Sort-Object
