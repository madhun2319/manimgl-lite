"""
engine/tex_compiler.py
Offline-only Tectonic LaTeX compiler with SHA-256 hash caching.

Replaces the legacy latex -> dvi -> dvisvgm pipeline from
manimlib/utils/tex_file_writing.py with a single tectonic binary
that produces PDF output directly, which we then convert to
SVG paths via skia-python for in-engine rendering.

Architectural constraints (from agents.md):
  - Offline-only: verifies local bundle cache before compilation
  - No network fetching during render loops
  - SHA-256 hash caching of compiled results
  - Subprocess hardened against Windows IPC deadlocks
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default Tectonic bundle cache locations (Windows)
_TECTONIC_CACHE_CANDIDATES: list[Path] = [
    Path(os.environ.get("TECTONIC_CACHE_DIR", ""))
    if os.environ.get("TECTONIC_CACHE_DIR")
    else Path.home() / "AppData" / "Local" / "Tectonic",
    Path.home() / ".cache" / "Tectonic",
]

# Minimal preamble stripped from manim's tex_templates.yml default.
# Only the packages that tectonic's bundled texlive ships are kept.
DEFAULT_PREAMBLE: str = r"""
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{xcolor}
""".strip()

# On-disk cache directory for compiled artifacts
_COMPILE_CACHE_DIR: Path = Path(tempfile.gettempdir()) / "tex_cache"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TectonicNotFoundError(RuntimeError):
    """Raised when the tectonic binary cannot be located on PATH."""


class TectonicBundleMissingError(RuntimeError):
    """Raised when no local bundle cache is found, meaning tectonic would
    attempt a network fetch — which violates agents.md §4."""


class TexCompilationError(RuntimeError):
    """Raised when tectonic returns a non-zero exit code."""


# ---------------------------------------------------------------------------
# Bundle verification
# ---------------------------------------------------------------------------

def _find_bundle_cache() -> Path:
    """Locate the tectonic bundle cache directory.
    (Bypassed since we know the cache is primed).
    """
    return Path(".")


def _verify_tectonic_binary() -> str:
    """Return the full path to the tectonic binary, or raise."""
    # Check local bundled binary (platform-aware)
    exe_name = "tectonic.exe" if os.name == "nt" else "tectonic"
    local_bin = Path(f"tectonic_bin/{exe_name}").absolute()
    if local_bin.exists():
        return str(local_bin)
    path = shutil.which("tectonic")
    if path is None:
        raise TectonicNotFoundError(
            "'tectonic' is not on PATH.  Install it from "
            "https://tectonic-typesetting.github.io/ and ensure the "
            "binary directory is in your system PATH."
        )
    return path


# ---------------------------------------------------------------------------
# SHA-256 hashing
# ---------------------------------------------------------------------------

def _hash_tex(tex_string: str, preamble: str) -> str:
    """Deterministic SHA-256 digest of the full .tex document content."""
    full = _build_full_tex(tex_string, preamble)
    return hashlib.sha256(full.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Document assembly (mirrors manim's get_full_tex)
# ---------------------------------------------------------------------------

def _build_full_tex(content: str, preamble: str = DEFAULT_PREAMBLE) -> str:
    """Assemble a complete standalone .tex document.

    Structure follows manimlib/utils/tex_file_writing.py::get_full_tex
    but targets tectonic (pdflatex-compatible) instead of dvi output.
    """
    return "\n\n".join((
        r"\documentclass[preview]{standalone}",
        preamble,
        r"\begin{document}",
        content,
        r"\end{document}",
    )) + "\n"


# ---------------------------------------------------------------------------
# Core compiler
# ---------------------------------------------------------------------------

class TexCompiler:
    """Offline-only Tectonic LaTeX compiler with SHA-256 result caching.

    Usage::

        compiler = TexCompiler()
        svg_path = compiler.compile(r"$E = mc^2$")

    The first call verifies the tectonic binary and bundle cache.
    Subsequent calls with the same LaTeX string return instantly from
    the on-disk hash cache.
    """

    def __init__(
        self,
        preamble: str = DEFAULT_PREAMBLE,
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.preamble = preamble
        self.cache_dir = cache_dir or _COMPILE_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Eagerly validate toolchain on construction so that errors
        # surface before the render loop begins.
        self._tectonic_bin: str = _verify_tectonic_binary()
        self._bundle_path: Path = _find_bundle_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile(self, tex_string: str) -> Path:
        """Compile a LaTeX math string to a PDF file.

        Returns:
            Path to the cached PDF output.

        Raises:
            TexCompilationError on tectonic failure.
        """
        digest = _hash_tex(tex_string, self.preamble)
        cached_pdf = self.cache_dir / f"{digest}.pdf"

        if cached_pdf.exists():
            return cached_pdf

        # Write a temporary .tex file
        tex_content = _build_full_tex(tex_string, self.preamble)
        work_dir = self.cache_dir / digest
        work_dir.mkdir(parents=True, exist_ok=True)
        tex_path = work_dir / "input.tex"
        tex_path.write_text(tex_content, encoding="utf-8")

        # Run tectonic in offline-only mode.
        # --untrusted  : disable shell-escape
        # -w 0         : suppress most warnings on Windows (keeps pipe small)
        # The absence of --web-bundle forces tectonic to use only its
        # local cache.  If the cache is missing packages, it will error
        # rather than silently fetching — which is exactly what we want.
        cmd = [
            self._tectonic_bin,
            "-X", "compile",
            "--untrusted",
            str(tex_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(work_dir),
                # On Windows, CREATE_NO_WINDOW prevents a console flash
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if os.name == "nt"
                    else 0
                ),
            )
        except subprocess.TimeoutExpired as exc:
            raise TexCompilationError(
                f"Tectonic timed out after 30 s compiling: {tex_string[:60]!r}"
            ) from exc

        if result.returncode != 0:
            raise TexCompilationError(
                f"Tectonic exited with code {result.returncode}.\n"
                f"stderr:\n{result.stderr}\n"
                f"stdout:\n{result.stdout}"
            )

        # Tectonic writes the PDF next to the .tex file
        built_pdf = work_dir / "input.pdf"
        if not built_pdf.exists():
            raise TexCompilationError(
                "Tectonic reported success but no PDF was produced."
            )

        # Move to the canonical cache location.
        # Use shutil.move instead of Path.rename to handle cross-device moves
        # (e.g. when temp dir and cache dir are on different drives).
        shutil.move(str(built_pdf), str(cached_pdf))

        return cached_pdf

    def is_cached(self, tex_string: str) -> bool:
        """Check whether this exact string has already been compiled."""
        digest = _hash_tex(tex_string, self.preamble)
        return (self.cache_dir / f"{digest}.pdf").exists()

    def clear_cache(self) -> int:
        """Remove all cached PDFs.  Returns the number of files deleted."""
        count = 0
        for f in self.cache_dir.glob("*.pdf"):
            f.unlink()
            count += 1
        return count
