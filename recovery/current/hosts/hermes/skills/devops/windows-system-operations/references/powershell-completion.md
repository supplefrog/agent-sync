# PowerShell completion engineering

PowerShell completion has two layers: PSReadLine controls what Tab does visually, while `TabExpansion2` and argument completers control available and ranked candidates. Bash-like behavior normally requires command names before paths in command position, command-specific arguments before paths in argument position, and paths as fallback.

Test at least root command completion, first subcommand, a nested positional argument, an unrelated completer such as Git, and one fallback/path-heavy case. Do not accept a shallow root-only test.

Use the command/native signature:

```powershell
Register-ArgumentCompleter -CommandName tool -Native -ScriptBlock {
  param($wordToComplete, $commandAst, $cursorPosition)
}
```

Use the five-argument signature only with `-ParameterName`. If a CLI emits bash/zsh/fish completion but not PowerShell, generate a small updateable native shim and include deeper provider/profile/tool/server positional values rather than translating only top-level verbs.

Measure profile startup before and after module changes. Lazy-load heavy completers on first relevant Tab invocation and avoid `Get-Module -ListAvailable` scans on every shell start because both import and discovery can dominate startup latency.
