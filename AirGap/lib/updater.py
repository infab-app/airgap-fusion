import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import config
from lib import github_client


@dataclass
class UpdateCheckResult:
    update_available: bool
    current_version: str
    latest_version: str
    release_notes: str
    download_url: str
    asset_name: str
    is_prerelease: bool
    error: str | None


@dataclass
class StagingResult:
    success: bool
    staging_path: Path | None
    error: str | None


def _parse_pre(pre: str) -> tuple:
    if not pre:
        return ()
    result = []
    for segment in pre.split("."):
        try:
            result.append((0, int(segment)))
        except ValueError:
            result.append((1, segment))
    return tuple(result)


def parse_version(version_str: str) -> tuple[tuple[int, ...], str]:
    v = version_str.lstrip("v")
    pre = ""
    if "-" in v:
        v, pre = v.split("-", 1)
    parts = tuple(int(p) for p in v.split("."))
    return parts, pre


def is_newer(latest: str, current: str) -> bool:
    lat_parts, lat_pre = parse_version(latest)
    cur_parts, cur_pre = parse_version(current)

    if lat_parts > cur_parts:
        return True
    if lat_parts < cur_parts:
        return False
    if lat_pre == "" and cur_pre != "":
        return True
    if lat_pre != "" and cur_pre == "":
        return False
    return _parse_pre(lat_pre) > _parse_pre(cur_pre)


def check_for_update(channel: str = "stable") -> UpdateCheckResult:
    current = config.VERSION
    release = github_client.fetch_latest_release(channel)

    if release is None:
        return UpdateCheckResult(
            update_available=False,
            current_version=current,
            latest_version="",
            release_notes="",
            download_url="",
            asset_name="",
            is_prerelease=False,
            error="Could not reach GitHub. Check your internet connection.",
        )

    tag = release.get("tag_name", "")
    latest = tag.lstrip("v")

    if not latest or not is_newer(latest, current):
        return UpdateCheckResult(
            update_available=False,
            current_version=current,
            latest_version=latest,
            release_notes="",
            download_url="",
            asset_name="",
            is_prerelease=release.get("prerelease", False),
            error=None,
        )

    download_url = ""
    asset_name = ""
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.startswith("AirGap") and name.endswith(".zip"):
            download_url = asset["browser_download_url"]
            asset_name = name
            break

    if not download_url:
        return UpdateCheckResult(
            update_available=True,
            current_version=current,
            latest_version=latest,
            release_notes=release.get("body", ""),
            download_url="",
            asset_name="",
            is_prerelease=release.get("prerelease", False),
            error="Release found but no downloadable zip asset attached.",
        )

    return UpdateCheckResult(
        update_available=True,
        current_version=current,
        latest_version=latest,
        release_notes=release.get("body", ""),
        download_url=download_url,
        asset_name=asset_name,
        is_prerelease=release.get("prerelease", False),
        error=None,
    )


def download_and_stage(result: UpdateCheckResult) -> StagingResult:
    staging_dir = config.UPDATE_STAGING_DIR

    try:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return StagingResult(False, None, f"Could not create staging directory: {e}")

    zip_path = staging_dir / result.asset_name
    if not github_client.download_asset(result.download_url, zip_path):
        return StagingResult(False, None, "Download failed. Please try again later.")

    checksums = github_client.download_checksums(f"v{result.latest_version}")
    if not checksums:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return StagingResult(
            False, None, "Could not download checksums for verification. Update aborted."
        )

    expected = checksums.get(result.asset_name)
    if not expected:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return StagingResult(
            False, None, f"No checksum found for {result.asset_name}. Update aborted."
        )

    actual = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    if actual != expected:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return StagingResult(
            False, None, "Checksum verification failed. Download may be corrupted."
        )

    if not zipfile.is_zipfile(zip_path):
        shutil.rmtree(staging_dir, ignore_errors=True)
        return StagingResult(False, None, "Downloaded file is not a valid zip archive.")

    extract_dir = staging_dir / "extracted"
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return StagingResult(False, None, "Zip extraction failed.")

    addin_dir = _find_addin_root(extract_dir)
    if addin_dir is None:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return StagingResult(
            False, None, "Invalid archive structure: missing AirGap.py or AirGap.manifest."
        )

    extracted_config = addin_dir / "config.py"
    if extracted_config.exists():
        text = extracted_config.read_text(encoding="utf-8")
        match = re.search(r"VERSION\s*=\s*['\"]([^'\"]+)['\"]", text)
        if match:
            extracted_ver = match.group(1)
            if extracted_ver != result.latest_version:
                shutil.rmtree(staging_dir, ignore_errors=True)
                return StagingResult(
                    False,
                    None,
                    f"Version mismatch: expected {result.latest_version}, got {extracted_ver}.",
                )

    pending = {
        "version": result.latest_version,
        "staging_path": str(addin_dir),
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }
    config.UPDATE_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.UPDATE_PENDING_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=2)
    tmp.replace(config.UPDATE_PENDING_FILE)

    return StagingResult(True, addin_dir, None)


def _find_addin_root(extract_dir: Path) -> Path | None:
    if (extract_dir / "AirGap.py").exists() and (extract_dir / "AirGap.manifest").exists():
        return extract_dir

    for child in extract_dir.iterdir():
        if (
            child.is_dir()
            and (child / "AirGap.py").exists()
            and (child / "AirGap.manifest").exists()
        ):
            return child
    return None
