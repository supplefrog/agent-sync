# Windows commands

Read before local Windows inspection. Use PowerShell and available native tools; the main router's shell snippets are POSIX examples, not PowerShell commands.

```powershell
$targetPath = 'C:\selected\app.asar'
Get-FileHash -LiteralPath $targetPath -Algorithm SHA256
Get-Command node,npm,rg,llvm-readobj,llvm-objdump,objdump,ilspycmd -ErrorAction SilentlyContinue
Get-Content -LiteralPath $targetPath -AsByteStream -TotalCount 64 | Format-Hex
```

Create a new task extraction directory and use `Copy-Item -LiteralPath` for copies. For archives, inventory first and validate every extraction destination remains inside that directory, including links. Never recursively remove an existing directory as a recon shortcut.

For Electron, use an available `@electron/asar` CLI or acquire it on demand with `npx -y @electron/asar extract <artifact> <fresh-directory>`. Inspect `app.asar.unpacked` alongside it. Read `package.json` through `Get-Content -Raw | ConvertFrom-Json`; search hidden bundler trees with `rg -uu`. For a minified file, use `rg -n -o '.{0,160}NEEDLE.{0,160}' <path>` with bounded matches. Preserve complete raw output in a task file when the preview is truncated.

For PE files, use available `llvm-readobj --file-headers --sections --coff-imports --coff-exports <path>` or `objdump -x <path>`; use an available format parser for resources. Missing imports/symbols in a bounded search do not prove absence. Managed .NET uses `ilspycmd`; NativeAOT and IL2CPP use the native/cloud route.

For SQLite, copy the database and any WAL coherently, then use available `sqlite3` or Python's `sqlite3.connect('file:<copy>?mode=ro', uri=True)`. Inspect schema and bounded rows; do not open the live original for writes.

Windows cannot supply `otool`, `lipo`, `codesign`, APFS clone copies or `brew`. Linux cloud can inspect portable bytes with appropriate tools; macOS-specific runtime or signing evidence still requires a compatible host. Report the unavailable evidence explicitly. Live browser, app and hardware work remains local through the existing authorized tools.
