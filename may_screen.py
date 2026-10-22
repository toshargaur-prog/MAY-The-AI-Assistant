"""Explicit one-shot screen inspection for MAY; screenshots are never persisted."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess


_SCREEN_ERROR_MARKER = re.compile(
    r"(?i)\b(?:error|exception|failed|failure|traceback|warning|denied|not found|"
    r"cannot|could not|unable to|timed out|timeout|crashed|fatal|invalid)\b|0x[0-9a-f]{4,}"
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|api[_ -]?key|token|secret|authorization)\b\s*[:=]\s*\S+"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
_API_TOKEN = re.compile(r"\b(?:AIza[0-9A-Za-z_-]{20,}|(?:sk|gh[pousr]|github_pat)_[A-Za-z0-9_-]{16,})\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_USER_PATH = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+")

_SCREEN_ERROR_PHRASES = (
    "explain this error", "explain the error", "explain that error", "explain this issue",
    "what is this error", "what s this error", "what does this error mean",
    "how do i fix this error", "how can i fix this error", "fix this error on my screen",
    "error on my screen", "look at this error", "explain the error on my screen",
    "what is wrong on my screen", "screen par error", "screen pe error",
    "screen par jo error hai", "screen pe jo error hai", "screen ka error",
    "meri screen par error", "mere screen pe error", "screen pe kya error hai",
    "ye error kya hai", "yeh error kya hai", "is error ko samjhao",
    "ye error samjhao", "yeh error samjhao", "is error ko kaise fix karu",
    "error ko kaise theek karu", "screen par jo error hai usse samjhao",
    "\u0938\u094d\u0915\u094d\u0930\u0940\u0928 \u092a\u0930 \u0915\u094d\u092f\u093e error \u0939\u0948",
    "\u092f\u0939 error \u0915\u094d\u092f\u093e \u0939\u0948",
    "\u0907\u0938 error \u0915\u094b \u0938\u092e\u091d\u093e\u0913",
    "\u0938\u094d\u0915\u094d\u0930\u0940\u0928 \u0915\u093e error \u092c\u0924\u093e\u0913",
)


def is_screen_error_request(text: str) -> bool:
    normalized = " ".join(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))
    return any(phrase in normalized for phrase in _SCREEN_ERROR_PHRASES)


def sanitize_screen_text(text: str, limit: int = 8000) -> str:
    if not text:
        return ""
    cleaned = text.replace("\x00", "")
    cleaned = _SECRET_ASSIGNMENT.sub(r"\1=[redacted]", cleaned)
    cleaned = _BEARER_TOKEN.sub("Bearer [redacted]", cleaned)
    cleaned = _API_TOKEN.sub("[redacted key]", cleaned)
    cleaned = _EMAIL.sub("[redacted email]", cleaned)
    cleaned = _USER_PATH.sub("[user path]", cleaned)
    lines: list[str] = []
    seen: set[str] = set()
    size = 0
    for raw_line in cleaned.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line or line.casefold() in seen:
            continue
        seen.add(line.casefold())
        line = line[:1200]
        remaining = limit - size
        if remaining <= 0:
            break
        line = line[:remaining]
        lines.append(line)
        size += len(line) + 1
    return "\n".join(lines)


def screen_error_search_query(text: str) -> str:
    if not text:
        return ""
    marked = [line.strip() for line in text.splitlines() if _SCREEN_ERROR_MARKER.search(line)]
    if not marked:
        return ""
    query = " ".join(marked[:3])
    query = _SECRET_ASSIGNMENT.sub(r"\1=[redacted]", query)
    query = _BEARER_TOKEN.sub("Bearer [redacted]", query)
    query = _API_TOKEN.sub("[redacted key]", query)
    query = _EMAIL.sub("[redacted email]", query)
    query = _USER_PATH.sub("[user path]", query)
    query = re.sub(r"\b[A-Za-z0-9_-]{48,}\b", "[long value]", query)
    return " ".join(query.split())[:240]


def ollama_model_supports_vision(model_name: str) -> bool:
    name = model_name.casefold().replace("-", "").replace("_", "").replace(".", "")
    return any(marker in name for marker in (
        "llava", "vision", "qwen25vl", "qwen3vl", "gemma3", "moondream",
        "minicpmv", "granite32vision", "internvl", "llama4",
    ))


def capture_screen_jpeg() -> bytes | None:
    """Capture the desktop to compressed in-memory JPEG bytes; never write a file."""
    try:
        from PIL import Image, ImageGrab
        try:
            screenshot = ImageGrab.grab(all_screens=True)
        except TypeError:
            screenshot = ImageGrab.grab()
        if screenshot.mode != "RGB":
            screenshot = screenshot.convert("RGB")
        resampling = getattr(Image, "Resampling", Image)
        screenshot.thumbnail((1600, 1600), resampling.LANCZOS)
        from io import BytesIO
        buffer = BytesIO()
        screenshot.save(buffer, format="JPEG", quality=68, optimize=True)
        return buffer.getvalue()
    except Exception:
        return None


def read_accessible_screen_text(own_process_id: int) -> str:
    """Read accessible text from visible non-MAY windows using Windows UI Automation."""
    if os.name != "nt":
        return ""
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        return ""
    script = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
$ownPid = __MAY_PID__
$root = [System.Windows.Automation.AutomationElement]::RootElement
$condition = [System.Windows.Automation.Condition]::TrueCondition
$windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $condition)
$titles = New-Object 'System.Collections.Generic.List[string]'
$lines = New-Object 'System.Collections.Generic.List[string]'
$keepTypes = @(50004,50005,50007,50017,50020,50024,50029,50030,50032,50033,50034,50035,50036)
$usedWindows = 0
foreach ($window in $windows) {
    if ($usedWindows -ge 6 -or $lines.Count -ge 260) { break }
    try {
        $windowInfo = $window.Current
        if ($windowInfo.ProcessId -eq $ownPid -or $windowInfo.IsOffscreen) { continue }
        $bounds = $windowInfo.BoundingRectangle
        if ($bounds.Width -lt 100 -or $bounds.Height -lt 60) { continue }
        $title = ([string]$windowInfo.Name).Trim()
        $usedWindows++
        if ($title -and -not $titles.Contains($title)) { [void]$titles.Add($title) }
        $nodes = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
        $limit = [Math]::Min($nodes.Count, 500)
        for ($i = 0; $i -lt $limit; $i++) {
            if ($lines.Count -ge 260) { break }
            try {
                $node = $nodes.Item($i)
                $info = $node.Current
                if ($info.IsOffscreen -or $info.IsPassword) { continue }
                if ($keepTypes -notcontains $info.ControlType.Id) { continue }
                $value = ([string]$info.Name).Trim()
                if ($info.ControlType.Id -eq 50004 -or $info.ControlType.Id -eq 50030) {
                    try {
                        $valuePattern = $node.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
                        $patternValue = ([string]$valuePattern.Current.Value).Trim()
                        if ($patternValue) { $value = $patternValue }
                    } catch {}
                }
                if (-not $value) { continue }
                if ($value.Length -gt 1200) { $value = $value.Substring(0,1200) }
                if (-not $lines.Contains($value)) { [void]$lines.Add($value) }
            } catch {}
        }
    } catch {}
}
$result = @{
    titles = @($titles.ToArray())
    text = [string]::Join([Environment]::NewLine, $lines.ToArray())
}
[Console]::Out.WriteLine((ConvertTo-Json -InputObject $result -Compress -Depth 3))
"""
    script = script.replace("__MAY_PID__", str(int(own_process_id)))
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=12, creationflags=flags, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    payload = None
    for line in reversed([line.strip() for line in result.stdout.splitlines() if line.strip()]):
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(payload, dict):
        return ""
    titles = payload.get("titles", [])
    text = payload.get("text", "")
    parts = [f"Window: {title}" for title in titles if isinstance(title, str) and title.strip()] if isinstance(titles, list) else []
    if isinstance(text, str) and text.strip():
        parts.append(text)
    return sanitize_screen_text("\n".join(parts))
