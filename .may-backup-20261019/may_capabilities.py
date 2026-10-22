"""Bounded file and document helpers for MAY's project workspace."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist",
    "build", ".next", ".idea", ".vscode", ".may-backups",
}
VISIBLE_CONFIG_DIRS = {".github", ".codex", ".agents", ".devcontainer", ".husky"}
SENSITIVE_NAMES = {
    ".env", ".env.local", ".env.production", "credentials.json",
    "secrets.json", "auth.json", ".npmrc", ".pypirc", ".netrc",
    "id_rsa", "id_ed25519", "known_hosts",
}
TEXT_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".html", ".css", ".scss", ".sass", ".less", ".json", ".md", ".mdx", ".txt", ".rst", ".toml",
    ".yaml", ".yml", ".ini", ".cfg", ".xml", ".sql", ".sh", ".bat",
    ".ps1", ".java", ".kt", ".go", ".rs", ".c", ".h", ".cpp", ".cs",
    ".swift", ".vue", ".svelte", ".astro", ".php", ".rb", ".dart", ".scala",
    ".gradle", ".tf", ".hcl", ".proto", ".graphql", ".gql", ".lua", ".r", ".tex",
    ".ipynb", ".env.example", ".gitignore",
}
TEXT_FILENAMES = {
    "dockerfile", "makefile", "license", ".env.example", ".gitignore",
    ".gitattributes", ".gitmodules", ".dockerignore", ".editorconfig",
    ".prettierrc", "justfile", "procfile",
}
MAX_FILE_BYTES = 256_000
MAX_WRITE_CHARS = 600_000


def _is_supported_text(path: Path) -> bool:
    return path.suffix.casefold() in TEXT_SUFFIXES or path.name.casefold() in TEXT_FILENAMES


def _is_sensitive(path: Path) -> bool:
    name = path.name.casefold()
    return (
        name in SENSITIVE_NAMES
        or name.startswith(".env.") and name != ".env.example"
        or path.suffix.casefold() in {".pem", ".key", ".p12", ".pfx"}
        or any(marker in name for marker in ("secret", "credential", "token", "api_key", "apikey"))
    )


def _inside(root: Path, relative_path: str) -> Path:
    base = root.expanduser().resolve(strict=True)
    raw = Path(relative_path.replace("\\", "/"))
    if raw.is_absolute() or not raw.parts or any(part in {".", ".."} for part in raw.parts):
        raise ValueError("Use a relative path inside the selected project folder.")
    candidate = (base / raw).resolve(strict=False)
    if not candidate.is_relative_to(base):
        raise ValueError("That path is outside the selected project folder.")
    if any(part.casefold() in IGNORED_DIRS for part in raw.parts):
        raise ValueError("MAY does not access generated or dependency folders.")
    return candidate


def list_project_files(root: Path, limit: int = 400) -> list[str]:
    """Return a bounded list of ordinary project files, omitting dependencies and secrets."""
    base = root.expanduser().resolve(strict=True)
    found: list[str] = []
    for current, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = sorted(
            directory for directory in dirs
            if directory.casefold() not in IGNORED_DIRS
            and (not directory.startswith(".") or directory.casefold() in VISIBLE_CONFIG_DIRS)
            and not (Path(current) / directory).is_symlink()
        )
        for filename in sorted(files, key=str.casefold):
            path = Path(current) / filename
            if path.is_symlink() or _is_sensitive(path):
                continue
            if not _is_supported_text(path):
                continue
            found.append(path.relative_to(base).as_posix())
            if len(found) >= limit:
                return found
    return found


def read_project_file(root: Path, relative_path: str) -> str:
    path = _inside(root, relative_path)
    if _is_sensitive(path):
        raise ValueError("MAY will not read key or credential files.")
    if not path.is_file() or not _is_supported_text(path):
        raise ValueError("That is not a supported text source file.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("That file is too large to read into the project conversation.")
    return path.read_text(encoding="utf-8", errors="replace")


def write_project_file(root: Path, relative_path: str, content: str) -> dict[str, str]:
    """Write one text file in the chosen workspace and preserve an existing copy."""
    raw_parts = Path(relative_path.replace("\\", "/")).parts
    if any(part.casefold() == "sources" for part in raw_parts):
        raise ValueError("The project's sources folder is read-only.")
    path = _inside(root, relative_path)
    base = root.expanduser().resolve(strict=True)
    if any(part.casefold() == "sources" for part in path.relative_to(base).parts):
        raise ValueError("The project's sources folder is read-only.")
    if _is_sensitive(path):
        raise ValueError("MAY will not write key or credential files.")
    if not _is_supported_text(path):
        raise ValueError("MAY can only create or edit supported text source files.")
    if not isinstance(content, str) or len(content) > MAX_WRITE_CHARS:
        raise ValueError("The new file content is too large.")
    backup_path = ""
    if path.exists():
        if not path.is_file():
            raise ValueError("The requested path is not a regular file.")
        backup_dir = base / ".may-backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_file = backup_dir / path.relative_to(base)
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_file)
        backup_path = backup_file.relative_to(base).as_posix()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=".may-write-", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return {"path": path.relative_to(base).as_posix(), "backup": backup_path}


def extract_pdf_text(path: Path, max_pages: int = 60, max_chars: int = 40_000) -> tuple[str, int]:
    """Extract selectable text from a bounded number of PDF pages."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support needs pypdf. Install MAY's requirements and restart.") from exc
    path = path.expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.casefold() != ".pdf":
        raise ValueError("Choose a PDF file.")
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("That PDF is over 100 MB; choose a smaller file.")
    reader = PdfReader(str(path))
    page_count = len(reader.pages)
    pieces: list[str] = []
    remaining = max_chars
    for index, page in enumerate(reader.pages[:max_pages], start=1):
        page_text = (page.extract_text() or "").strip()
        if not page_text:
            continue
        piece = f"[Page {index}]\n{page_text}"
        piece = piece[:remaining]
        if piece:
            pieces.append(piece)
            remaining -= len(piece)
        if remaining <= 0:
            break
    if page_count > max_pages:
        pieces.append(f"[Only the first {max_pages} pages were read; this PDF has {page_count} pages.]")
    return "\n\n".join(pieces), page_count


def export_chat_pdf(path: Path, title: str, messages: list[tuple[str, str]]) -> None:
    """Create a paginated, styled PDF from recent MAY conversation text."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer
    except ImportError as exc:
        raise RuntimeError("PDF export needs reportlab. Install MAY's requirements and restart.") from exc

    font_regular, font_bold = "Helvetica", "Helvetica-Bold"
    font_options = (
        (
            Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts" / "Nirmala.ttf",
            Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts" / "NirmalaB.ttf",
            "MAYNirmala",
        ),
        (
            Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts" / "Mangal.ttf",
            Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts" / "Mangalb.ttf",
            "MAYMangal",
        ),
        (
            Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
            Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts" / "segoeuib.ttf",
            "MAYSegoe",
        ),
    )
    for regular_path, bold_path, font_name in font_options:
        if regular_path.is_file():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(regular_path)))
                bold_font_name = font_name
                if bold_path.is_file():
                    bold_font_name = font_name + "-Bold"
                    pdfmetrics.registerFont(TTFont(bold_font_name, str(bold_path)))
                pdfmetrics.registerFontFamily(
                    font_name,
                    normal=font_name,
                    bold=bold_font_name,
                    italic=font_name,
                    boldItalic=bold_font_name,
                )
                font_regular = font_name
                font_bold = bold_font_name
                break
            except Exception:
                continue

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MayTitle", parent=styles["Title"], fontName=font_bold,
        fontSize=22, leading=27, textColor=colors.HexColor("#123d46"),
        alignment=TA_LEFT, spaceAfter=8 * mm,
    ))
    styles.add(ParagraphStyle(
        name="MaySpeaker", parent=styles["Heading3"], fontName=font_bold,
        fontSize=9, leading=13, textColor=colors.HexColor("#087e78"),
        spaceBefore=5 * mm, spaceAfter=1.5 * mm, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="MayBody", parent=styles["BodyText"], fontName=font_regular,
        fontSize=10, leading=15, textColor=colors.HexColor("#18252e"),
        spaceAfter=3 * mm, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="MayBullet", parent=styles["MayBody"], leftIndent=5 * mm,
        firstLineIndent=-3 * mm, bulletIndent=0,
    ))
    styles.add(ParagraphStyle(
        name="MaySection", parent=styles["Heading2"], fontName=font_bold,
        fontSize=13, leading=17, textColor=colors.HexColor("#123d46"),
        spaceBefore=4 * mm, spaceAfter=2 * mm, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="MaySubsection", parent=styles["Heading3"], fontName=font_bold,
        fontSize=11, leading=15, textColor=colors.HexColor("#236b69"),
        spaceBefore=3 * mm, spaceAfter=1.5 * mm, keepWithNext=True,
    ))

    class MayDocTemplate(BaseDocTemplate):
        def __init__(self, filename: str) -> None:
            super().__init__(filename, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
                             topMargin=22 * mm, bottomMargin=20 * mm, title=title, author="MAY")
            frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                          id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            self.addPageTemplates([PageTemplate(id="may", frames=[frame], onPage=self.draw_chrome)])

        def draw_chrome(self, canvas, document) -> None:
            canvas.saveState()
            width, height = A4
            canvas.setStrokeColor(colors.HexColor("#d4e8e4"))
            canvas.setLineWidth(0.6)
            canvas.line(20 * mm, height - 15 * mm, width - 20 * mm, height - 15 * mm)
            canvas.setFont(font_regular, 8)
            canvas.setFillColor(colors.HexColor("#63817f"))
            canvas.drawString(20 * mm, height - 12 * mm, "MAY  ·  PERSONAL ASSISTANT")
            canvas.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)
            canvas.drawString(20 * mm, 9 * mm, "Created with MAY")
            canvas.drawRightString(width - 20 * mm, 9 * mm, f"{document.page}")
            canvas.restoreState()

    story = [Paragraph(escape(title.strip() or "MAY conversation"), styles["MayTitle"])]

    def flush_paragraph(lines: list[str]) -> None:
        if lines:
            markup = "<br/>".join(lines)
            markup = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", markup)
            story.append(Paragraph(markup, styles["MayBody"]))
            lines.clear()

    for speaker, content in messages:
        if not content.strip():
            continue
        story.append(Paragraph(escape(speaker.upper()), styles["MaySpeaker"]))
        paragraph_lines: list[str] = []
        for raw_line in content.strip().splitlines():
            line = raw_line.strip()
            if not line:
                flush_paragraph(paragraph_lines)
                story.append(Spacer(1, 1.5 * mm))
                continue
            heading = re.match(r"^(#{1,3})\s+(.+)$", line)
            if heading:
                flush_paragraph(paragraph_lines)
                style = styles["MaySection"] if len(heading.group(1)) <= 2 else styles["MaySubsection"]
                story.append(Paragraph(escape(heading.group(2)), style))
                continue
            bullet = re.match(r"^(?:[-*•])\s+(.+)$", line)
            numbered = re.match(r"^(\d+[.)])\s+(.+)$", line)
            if bullet:
                flush_paragraph(paragraph_lines)
                story.append(Paragraph("- " + escape(bullet.group(1)), styles["MayBullet"]))
                continue
            if numbered:
                flush_paragraph(paragraph_lines)
                story.append(Paragraph(escape(numbered.group(1)) + " " + escape(numbered.group(2)), styles["MayBullet"]))
                continue
            if re.fullmatch(r"[-_]{3,}", line):
                flush_paragraph(paragraph_lines)
                continue
            paragraph_lines.append(escape(line))
        flush_paragraph(paragraph_lines)
    if not messages:
        story.append(Paragraph("No conversation is available to export yet.", styles["MayBody"]))
    MayDocTemplate(str(path)).build(story)


def is_project_edit_request(text: str) -> bool:
    """Only expose project write tools when the user clearly asks for a change."""
    query = text.casefold()
    actions = (
        "fix", "edit", "update", "change", "modify", "implement", "add ", "make ",
        "create ", "build ", "refactor", "remove", "delete", "repair",
        "optimize", "improve", "rewrite", "likh do", "bana do",
        "theek kar", "sudhar", "jod do", "हटा", "बदल", "बनाओ", "लिखो",
        "सुधार", "ठीक", "जोड़", "जोड़ो",
    )
    targets = (
        "project", "code", "file", "app", "website", "site", "repo", "repository",
        "script", "module", "bug", "feature", "button", "screen", "page", "folder",
        "function", "this", "that", " it ", "isko", "isse", "ise", "iske andar",
        "प्रोजेक्ट", "कोड", "फाइल", "ऐप", "इसे", "इसको",
    )
    padded = f" {query} "
    return any(action in query for action in actions) and any(target in padded for target in targets)
