from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
import warnings
from pathlib import Path


DEFAULT_STANZA_PROCESSORS = "tokenize,pos,lemma"
DEFAULT_UDPIPE_MODEL_FILENAME = "ancient_greek-perseus-ud-2.4-190531.udpipe"
DEFAULT_UDPIPE_MODEL_URL = (
    "https://raw.githubusercontent.com/jwijffels/udpipe.models.ud.2.4/master/"
    "inst/udpipe-ud-2.4-190531/ancient_greek-perseus-ud-2.4-190531.udpipe"
)
# SHA-256 of the official model file (None = skip hash verification)
_UDPIPE_MODEL_SHA256: str | None = None
_DOWNLOAD_TIMEOUT_SEC = 120


def default_models_root(workspace: str | Path) -> Path:
    root = Path(workspace) / "models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_stanza_model_dir(workspace: str | Path) -> Path:
    target = default_models_root(workspace) / "stanza"
    target.mkdir(parents=True, exist_ok=True)
    return target


def default_udpipe_model_path(workspace: str | Path) -> Path:
    target_dir = default_models_root(workspace) / "udpipe"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / DEFAULT_UDPIPE_MODEL_FILENAME


def stanza_resources_available(model_dir: str | Path) -> bool:
    model_dir = Path(model_dir)
    return (model_dir / "resources.json").exists() and (model_dir / "grc").exists()


def ensure_stanza_resources(model_dir: str | Path) -> Path:
    from .analyzers import check_stanza_available

    available, message = check_stanza_available()
    if not available:
        raise RuntimeError(message)

    target = Path(model_dir)
    target.mkdir(parents=True, exist_ok=True)
    if stanza_resources_available(target):
        return target

    import stanza

    stanza.download(
        "grc",
        model_dir=str(target),
        processors=DEFAULT_STANZA_PROCESSORS,
        logging_level="WARN",
    )
    return target


def udpipe_model_available(model_path: str | Path) -> bool:
    return Path(model_path).exists()


def _verify_sha256(path: Path, expected: str) -> bool:
    sha256 = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected


def ensure_udpipe_model(model_path: str | Path) -> Path:
    from .analyzers import check_udpipe_available

    available, message = check_udpipe_available()
    if not available:
        raise RuntimeError(message)

    target = Path(model_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        if _UDPIPE_MODEL_SHA256 and not _verify_sha256(target, _UDPIPE_MODEL_SHA256):
            warnings.warn(
                f"UDPipe model at {target} failed SHA-256 verification. "
                "Re-downloading."
            )
            target.unlink()
        else:
            return target

    # Download to a temporary file; move atomically only on success.
    # This prevents a partial download from masquerading as a valid model file.
    tmp_fd, tmp_name = tempfile.mkstemp(
        suffix=".udpipe.tmp", dir=target.parent
    )
    tmp_path = Path(tmp_name)
    try:
        req = urllib.request.Request(
            DEFAULT_UDPIPE_MODEL_URL,
            headers={"User-Agent": "greek-corpus-pipeline/1.0"},
        )
        with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_SEC) as response, \
                open(tmp_fd, "wb") as out_fh:
            shutil.copyfileobj(response, out_fh)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    if _UDPIPE_MODEL_SHA256 and not _verify_sha256(tmp_path, _UDPIPE_MODEL_SHA256):
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            "Downloaded UDPipe model failed SHA-256 verification. "
            "The file may be corrupt or the URL has changed."
        )

    shutil.move(str(tmp_path), str(target))
    return target


# ---------------------------------------------------------------------------
# The identity of a model, for the provenance of a comparison
# ---------------------------------------------------------------------------

def _fingerprint_tree(root: Path, patterns: tuple[str, ...] = ("*",)) -> str:
    """The fingerprint of a tree of files: relative path and size.

    It does not read the bytes of the models, which are hundreds of megabytes: name and
    size are enough to distinguish a replaced resource from one left where it was, and
    that is all that is needed to say whether a saved comparison was produced with these
    files or with others.
    """
    if not root.exists():
        return ""
    voci: list[str] = []
    for pattern in patterns:
        for percorso in sorted(root.rglob(pattern)):
            if percorso.is_file():
                voci.append(f"{percorso.relative_to(root).as_posix()}:{percorso.stat().st_size}")
    if not voci:
        return ""
    return hashlib.sha256("\n".join(sorted(voci)).encode("utf-8")).hexdigest()[:16]


def stanza_identity(model_dir: str | Path) -> tuple[str, str]:
    """Version of the Stanza library and fingerprint of the installed resources."""
    try:
        import stanza
        versione = getattr(stanza, "__version__", "unknown")
    except ImportError:
        versione = "not installed"
    return versione, _fingerprint_tree(Path(model_dir))


def udpipe_identity(model_path: str | Path) -> tuple[str, str]:
    """Version of the UDPipe library and fingerprint of the model file."""
    try:
        import ufal.udpipe as _udpipe
        versione = getattr(_udpipe, "__version__", "unknown")
    except ImportError:
        versione = "not installed"
    percorso = Path(model_path)
    if not percorso.exists():
        return versione, ""
    impronta = hashlib.sha256(
        f"{percorso.name}:{percorso.stat().st_size}".encode("utf-8")).hexdigest()[:16]
    return versione, impronta
