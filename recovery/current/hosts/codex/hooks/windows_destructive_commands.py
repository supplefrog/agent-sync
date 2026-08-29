#!/usr/bin/env python3
"""Claim: This PreToolUse hook blocks high-confidence catastrophic Windows or wrapped WSL shell commands while preserving safe inspection and scoped file operations."""

from __future__ import annotations

import base64
import json
import ntpath
import os
import re
import sys
from typing import Iterable


DELETE_COMMANDS = {"remove-item", "rm", "ri", "del", "erase", "rd", "rmdir"}
DISK_COMMANDS = {"clear-disk", "format-volume", "remove-partition", "initialize-disk"}
HELP_SWITCHES = {"/?", "-?", "--help"}
PATH_PARAMETERS = {"-path", "-literalpath"}
VALUE_PARAMETERS = {
    "-filter",
    "-include",
    "-exclude",
    "-credential",
    "-stream",
    "-erroraction",
    "-warningaction",
    "-informationaction",
    "-progressaction",
    "-errorvariable",
    "-warningvariable",
    "-informationvariable",
    "-outvariable",
    "-outbuffer",
    "-pipelinevariable",
}


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            separators=(",", ":"),
        )
    )


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def strip_comments(text: str) -> str:
    result: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if escaped:
            result.append(char)
            escaped = False
            index += 1
            continue
        if char == "`":
            result.append(char)
            escaped = True
            index += 1
            continue
        if quote:
            result.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            result.append(char)
            index += 1
            continue
        if char == "#" and (index == 0 or text[index - 1].isspace()):
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def split_powershell_segments(text: str) -> list[str]:
    segments: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    escaped = False
    for char in strip_comments(text):
        if escaped:
            buffer.append(char)
            escaped = False
            continue
        if char == "`":
            buffer.append(char)
            escaped = True
            continue
        if quote:
            buffer.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            buffer.append(char)
            continue
        if char in ";|&\r\n{}()":
            segment = "".join(buffer).strip()
            if segment:
                segments.append(segment)
            buffer.clear()
            continue
        buffer.append(char)
    segment = "".join(buffer).strip()
    if segment:
        segments.append(segment)
    return segments


TOKEN_PATTERN = re.compile(r"""'(?:[^']*)'|"(?:`.|[^"])*"|[^\s]+""")


def powershell_tokens(segment: str) -> list[str]:
    return [unquote(match.group(0)).strip(",") for match in TOKEN_PATTERN.finditer(segment)]


def command_name(value: str) -> str:
    name = ntpath.basename(unquote(value)).lower()
    return re.sub(r"\.(?:exe|com|cmd|bat)$", "", name)


def expand_known_path(value: str, cwd: str) -> str | None:
    candidate = unquote(value).strip()
    if not candidate:
        return None

    home = os.path.expanduser("~")
    substitutions = (
        (r"(?i)^\$\{?HOME\}?(?=[\\/]|$)", home),
        (r"(?i)^\$env:USERPROFILE(?=[\\/]|$)", home),
        (r"(?i)^%USERPROFILE%(?=[\\/]|$)", home),
    )
    candidate = re.sub(r"(?i)^Microsoft\.PowerShell\.Core\\FileSystem::", "", candidate)
    for pattern, replacement in substitutions:
        candidate = re.sub(pattern, lambda _match, value=replacement: value, candidate)
    if candidate == "~":
        candidate = home
    elif candidate.startswith(("~\\", "~/")):
        candidate = ntpath.join(home, candidate[2:])

    candidate = os.path.expandvars(candidate)
    candidate = re.sub(r"[\\/](?:\*|\*\.\*)$", "", candidate)
    if candidate in {"/", "\\"}:
        drive, _tail = ntpath.splitdrive(cwd)
        candidate = drive + "\\"

    if re.match(r"^[A-Za-z]+:", candidate) and not re.match(r"^[A-Za-z]:[\\/]", candidate):
        return None
    if not (ntpath.isabs(candidate) or candidate.startswith("\\\\")):
        candidate = ntpath.join(cwd, candidate)

    try:
        normalized = ntpath.normpath(candidate)
    except (TypeError, ValueError):
        return None
    drive, tail = ntpath.splitdrive(normalized)
    if drive and tail in {"", "\\", "/"}:
        return drive
    return normalized.rstrip("\\/")


def protected_paths(cwd: str) -> set[str]:
    home = os.path.expanduser("~")
    drive, _tail = ntpath.splitdrive(home)
    values = {
        drive,
        ntpath.join(drive + "\\", "Users") if drive else "",
        home,
        ntpath.join(home, ".codex"),
        ntpath.join(home, "Documents"),
        ntpath.join(home, "Documents", "Codex"),
        cwd,
        os.environ.get("SystemRoot", ""),
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        os.environ.get("ProgramData", ""),
    }
    return {
        normalized.casefold()
        for value in values
        if value and (normalized := expand_known_path(value, cwd))
    }


def is_protected_path(value: str, cwd: str) -> bool:
    normalized = expand_known_path(value, cwd)
    if not normalized:
        return False
    drive, tail = ntpath.splitdrive(normalized)
    if drive and tail in {"", "\\", "/"}:
        return True
    return normalized.casefold() in protected_paths(cwd)


def safe_whatif(arguments: Iterable[str]) -> bool:
    return any(re.fullmatch(r"(?i)-WhatIf(?::(?:\$?true))?", argument) for argument in arguments)


def deletion_targets(arguments: list[str]) -> list[str]:
    targets: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        lowered = argument.lower()
        if lowered in PATH_PARAMETERS:
            if index + 1 < len(arguments):
                targets.append(arguments[index + 1])
                index += 2
                continue
        if lowered in VALUE_PARAMETERS:
            index += 2
            continue
        if argument.startswith(("-", "/")):
            index += 1
            continue
        targets.append(argument)
        index += 1
    return targets


def split_unix_segments(text: str) -> list[str]:
    segments: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    escaped = False
    for char in text:
        if escaped:
            buffer.append(char)
            escaped = False
            continue
        if char == "\\" and quote != "'":
            buffer.append(char)
            escaped = True
            continue
        if quote:
            buffer.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            buffer.append(char)
            continue
        if char in ";|&\r\n":
            segment = "".join(buffer).strip()
            if segment:
                segments.append(segment)
            buffer.clear()
            continue
        buffer.append(char)
    segment = "".join(buffer).strip()
    if segment:
        segments.append(segment)
    return segments


UNIX_TOKEN_PATTERN = re.compile(r"""'(?:[^']*)'|"(?:\\.|[^"])*"|[^\s]+""")


def unix_tokens(segment: str) -> list[str]:
    return [unquote(match.group(0)) for match in UNIX_TOKEN_PATTERN.finditer(segment)]


def is_protected_unix_target(target: str) -> bool:
    value = unquote(target).rstrip("/")
    value = re.sub(r"/(?:\*|\{\*,\.\*\})$", "", value)
    value = value or "/"
    if value in {"/", "~", "$HOME", "${HOME}", "/home"}:
        return True
    if re.fullmatch(r"(?:~|\$HOME|\$\{HOME\})/(?:\*|\.\*)?", value):
        return True
    if re.fullmatch(r"/home/[^/]+", value):
        return True
    if re.fullmatch(r"/mnt/[a-z]", value, re.IGNORECASE):
        return True
    if re.fullmatch(
        r"/mnt/[a-z]/Users(?:/[^/]+(?:/Documents(?:/Codex)?)?)?",
        value,
        re.IGNORECASE,
    ):
        return True
    return bool(
        re.fullmatch(
            r"/mnt/[a-z]/(?:Windows|ProgramData|Program Files|Program Files \(x86\))",
            value,
            re.IGNORECASE,
        )
    )


def unix_reason(text: str) -> str | None:
    for segment in split_unix_segments(text):
        tokens = unix_tokens(segment)
        index = 0
        while index < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[index]):
            index += 1
        if index < len(tokens) and tokens[index] == "sudo":
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
        if index >= len(tokens):
            continue

        name = os.path.basename(tokens[index]).lower()
        arguments = tokens[index + 1 :]
        if name == "rm":
            recursive = any(
                argument == "--recursive" or re.fullmatch(r"-[A-Za-z]*r[A-Za-z]*", argument)
                for argument in arguments
            )
            force = any(
                argument == "--force" or re.fullmatch(r"-[A-Za-z]*f[A-Za-z]*", argument)
                for argument in arguments
            )
            targets = [argument for argument in arguments if not argument.startswith("-")]
            if recursive and force:
                for target in targets:
                    if is_protected_unix_target(target):
                        return f"Blocked recursive forced deletion of protected Unix/WSL target '{target}'."
        if name.startswith("mkfs") or name == "wipefs":
            return f"Blocked filesystem-formatting command '{name}'."
        if name == "diskutil" and arguments and arguments[0] in {
            "eraseDisk",
            "eraseVolume",
            "partitionDisk",
        }:
            return f"Blocked destructive diskutil operation '{arguments[0]}'."
        if name == "dd" and any(argument.startswith("of=/dev/") for argument in arguments):
            return "Blocked raw-device overwrite through dd."
        if name == "shred" and any(argument.startswith("/dev/") for argument in arguments):
            return "Blocked raw-device shredding."
    return None


def wrapper_payload(arguments: list[str], switches: set[str]) -> str | None:
    for index, argument in enumerate(arguments):
        if argument.lower() in switches and index + 1 < len(arguments):
            return " ".join(arguments[index + 1 :])
    return None


def powershell_reason(text: str, cwd: str, depth: int = 0) -> str | None:
    if depth > 3:
        return None
    for segment in split_powershell_segments(text):
        tokens = powershell_tokens(segment)
        if not tokens:
            continue
        while tokens and tokens[0] in {"&", "."}:
            tokens.pop(0)
        if not tokens:
            continue

        name = command_name(tokens[0])
        arguments = tokens[1:]
        if name in DELETE_COMMANDS and not safe_whatif(arguments):
            for target in deletion_targets(arguments):
                if is_protected_path(target, cwd):
                    return f"Blocked deletion of protected Windows target '{target}'."
        if name in DISK_COMMANDS and not safe_whatif(arguments):
            return f"Blocked destructive disk or partition command '{name}'."
        if name == "diskpart" and not (arguments and set(arguments) <= HELP_SWITCHES):
            return "Blocked diskpart; its command stream can erase or repartition disks."
        if name == "format" and not (arguments and set(arguments) <= HELP_SWITCHES):
            return "Blocked filesystem formatting through format.com."

        if name in {"pwsh", "powershell"}:
            encoded = wrapper_payload(arguments, {"-encodedcommand", "-enc", "-e"})
            if encoded:
                try:
                    decoded = base64.b64decode(encoded).decode("utf-16le")
                except (ValueError, UnicodeDecodeError):
                    decoded = ""
                if decoded and (reason := powershell_reason(decoded, cwd, depth + 1)):
                    return reason
            inner = wrapper_payload(arguments, {"-command", "-c"})
            if inner and (reason := powershell_reason(inner, cwd, depth + 1)):
                return reason

        if name == "cmd":
            inner = wrapper_payload(arguments, {"/c", "/k"})
            if inner and (reason := powershell_reason(inner, cwd, depth + 1)):
                return reason

        if name in {"wsl", "bash", "sh", "zsh"}:
            inner = wrapper_payload(arguments, {"-c", "-lc"})
            if inner and (reason := unix_reason(inner)):
                return reason
            if name == "wsl":
                for index, argument in enumerate(arguments):
                    if command_name(argument) in {"rm", "mkfs", "wipefs", "dd", "shred", "diskutil"}:
                        if reason := unix_reason(" ".join(arguments[index:])):
                            return reason
    return None


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw.lstrip("\ufeff"))
        tool_input = payload.get("tool_input")
        if isinstance(tool_input, str):
            command = tool_input
        elif isinstance(tool_input, dict):
            command = tool_input.get("command")
        else:
            command = None
        if not isinstance(command, str) or not command.strip():
            return 0
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        reason = powershell_reason(command, cwd)
        if reason:
            deny(reason)
        return 0
    except Exception:
        # Fail open on parser/runtime faults so the guard cannot disable the shell.
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
