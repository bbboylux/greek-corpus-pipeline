from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile


def _t(key: str, fallback: str, *args: object) -> str:
    """The visible text, in the language of the interface, with English as the fallback.

    This message ends up in a warning window, so it follows the chosen language; the
    fallback exists because the module must also work without an interface.
    """
    try:
        from gui_qt.i18n import tr                     # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return fallback.format(*args) if args else fallback
    text = tr(key, *args)
    if text == key:
        return fallback.format(*args) if args else fallback
    return text


_TREE_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?"
    r"(?:/tree/(?P<branch>[^/]+)(?:/(?P<subpath>.+))?)?/?$"
)


@dataclass(frozen=True)
class GitHubTreeLocation:
    owner: str
    repo: str
    branch: str | None
    subpath: str


def parse_github_tree_url(url: str) -> GitHubTreeLocation:
    match = _TREE_URL_RE.match(url.strip())
    if not match:
        raise ValueError(
            "Expected a GitHub repository or tree URL such as "
            "https://github.com/owner/repo/tree/branch/path"
        )

    return GitHubTreeLocation(
        owner=urllib.parse.unquote(match.group("owner")),
        repo=urllib.parse.unquote(match.group("repo")),
        branch=urllib.parse.unquote(match.group("branch")) if match.group("branch") else None,
        subpath=urllib.parse.unquote((match.group("subpath") or "").strip("/")),
    )


def _download_archive(location: GitHubTreeLocation, destination: Path, branch: str) -> Path:
    archive_url = (
        f"https://codeload.github.com/{location.owner}/{location.repo}/zip/refs/heads/{branch}"
    )
    archive_path = destination / f"{location.repo}-{branch}.zip"
    urllib.request.urlretrieve(archive_url, archive_path)
    return archive_path


def download_github_tree(url: str, destination: str | Path) -> Path:
    location = parse_github_tree_url(url)
    destination_path = Path(destination).resolve()
    destination_path.mkdir(parents=True, exist_ok=True)

    candidate_branches = [location.branch] if location.branch else ["main", "master"]
    archive_path: Path | None = None
    selected_branch: str | None = None
    last_error: Exception | None = None

    for branch in candidate_branches:
        if not branch:
            continue
        try:
            archive_path = _download_archive(location, destination_path, branch)
            selected_branch = branch
            break
        except urllib.error.HTTPError as exc:
            last_error = exc

    if archive_path is None or selected_branch is None:
        raise RuntimeError(
            f"Unable to download {url}. "
            "If the URL points to a repository root, specify the branch explicitly."
        ) from last_error

    extraction_root = destination_path / f"{location.repo}-{selected_branch}"
    if extraction_root.exists():
        shutil.rmtree(extraction_root)

    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination_path)

    source_root = extraction_root
    if location.subpath:
        source_root = extraction_root / location.subpath

    if not source_root.exists():
        raise FileNotFoundError(
            f"Downloaded the repository archive, but the requested subpath '{location.subpath}' "
            f"was not found in branch '{selected_branch}'."
        )

    return source_root


# ── Downloading a declared sample instead of a whole repository ──────────────
#
# GLAUx weighs twenty million records and about three gigabytes. A button that
# downloaded the complete archive would be unusable: the program would fill up with data
# that nobody could then inspect, and the machine would stop. But the external test of
# the article does not use the whole of GLAUx — it uses a sample drawn with a declared
# procedure. Downloading that sample, and nothing else, is therefore the right thing to
# do for two reasons: the program remains usable, and whoever reads the article obtains
# exactly the corpus on which the numbers were computed.

_RAW_URL = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"


def download_github_files(
    owner: str,
    repo: str,
    branch: str,
    paths: list[str],
    destination: str | Path,
    progress: "callable | None" = None,
) -> Path:
    """Download only the files indicated, one by one, and return the folder.

    A three-gigabyte archive from which to extract forty files is a waste of bandwidth
    and disk by three orders of magnitude; the single files are taken from the “raw”
    URL, which requires no authentication for a public repository.
    """
    destination_path = Path(destination).resolve()
    destination_path.mkdir(parents=True, exist_ok=True)
    scaricati = 0
    for index, path in enumerate(paths, start=1):
        target = destination_path / Path(path).name
        if target.exists() and target.stat().st_size > 0:
            scaricati += 1
            if progress:
                progress(index, len(paths), f"{target.name} (already present)")
            continue
        url = _RAW_URL.format(owner=owner, repo=repo, branch=branch,
                              path=urllib.parse.quote(path))
        try:
            urllib.request.urlretrieve(url, target)
            scaricati += 1
        except urllib.error.HTTPError as exc:
            if target.exists():
                target.unlink()
            raise RuntimeError(_t(
                "github.err.download",
                "Could not download {0} from {1}: {2}. Check the connection, or "
                "download the repository by hand and load it as a folder.",
                path, f"{owner}/{repo}@{branch}", exc)) from exc
        if progress:
            progress(index, len(paths), target.name)
    if not scaricati:
        raise RuntimeError("No file was downloaded: the sample list is empty.")
    return destination_path
