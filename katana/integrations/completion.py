"""bash / zsh / PowerShell için kabuk tamamlama script'leri üretir."""

from katana.converters import all_source_extensions

# argparse'taki uzun bayraklarla eşleşir.
OPTIONS = [
    "--output", "--to", "--from", "--recursive", "--list-formats", "--format",
    "--on-conflict", "--name", "--dry-run", "--log", "--undo", "--pick",
    "--install-context-menu", "--uninstall-context-menu", "--jobs", "--watch",
    "--profile", "--save-profile", "--quality", "--resize", "--watermark",
    "--video-height", "--audio-bitrate", "--trim-start", "--trim-end",
    "--zip-output", "--extract", "--merge", "--pages", "--compress", "--rotate",
    "--completion", "--help",
]


def _formats() -> list[str]:
    return sorted({e.lstrip(".") for e in all_source_extensions()})


def bash() -> str:
    opts = " ".join(OPTIONS)
    fmts = " ".join(_formats())
    return f"""# katana bash tamamlama — kaynak: source <(katana --completion bash)
_katana() {{
    local cur prev
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    case "$prev" in
        --to|--from) COMPREPLY=( $(compgen -W "{fmts}" -- "$cur") ); return ;;
        --on-conflict) COMPREPLY=( $(compgen -W "overwrite skip rename" -- "$cur") ); return ;;
        --format) COMPREPLY=( $(compgen -W "table json md" -- "$cur") ); return ;;
        --completion) COMPREPLY=( $(compgen -W "bash zsh powershell" -- "$cur") ); return ;;
    esac
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $(compgen -W "{opts}" -- "$cur") )
    else
        COMPREPLY=( $(compgen -f -- "$cur") )
    fi
}}
complete -F _katana katana
"""


def zsh() -> str:
    return "autoload -U +X bashcompinit && bashcompinit\n" + bash()


def powershell() -> str:
    opts = ", ".join(f"'{o}'" for o in OPTIONS)
    fmts = ", ".join(f"'{f}'" for f in _formats())
    return f"""# katana PowerShell tamamlama — profil'e ekleyin: katana --completion powershell | Out-String | Invoke-Expression
Register-ArgumentCompleter -Native -CommandName katana -ScriptBlock {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $opts = @({opts})
    $fmts = @({fmts})
    $tokens = $commandAst.CommandElements
    $prev = if ($tokens.Count -ge 2) {{ $tokens[$tokens.Count - 2].ToString() }} else {{ '' }}
    $pool = switch ($prev) {{
        '--to' {{ $fmts }}
        '--from' {{ $fmts }}
        '--on-conflict' {{ @('overwrite','skip','rename') }}
        '--format' {{ @('table','json','md') }}
        '--completion' {{ @('bash','zsh','powershell') }}
        default {{ $opts }}
    }}
    $pool | Where-Object {{ $_ -like "$wordToComplete*" }} |
        ForEach-Object {{ [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }}
}}
"""


def script_for(shell: str) -> str:
    return {"bash": bash, "zsh": zsh, "powershell": powershell}[shell]()
