import json
import urllib.error
import urllib.request
from pathlib import Path

import config


def fetch_latest_release(channel: str) -> dict | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"AirGap/{config.VERSION}",
    }
    base = f"{config.GITHUB_API_BASE}/repos/{config.GITHUB_OWNER}/{config.GITHUB_REPO}"

    try:
        if channel == "stable":
            url = f"{base}/releases/latest"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=config.UPDATE_CHECK_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        else:
            url = f"{base}/releases?per_page=20"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=config.UPDATE_CHECK_TIMEOUT) as resp:
                releases = json.loads(resp.read().decode("utf-8"))
            if releases:
                return releases[0]
            return None
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return None


def download_asset(url: str, dest_path: Path) -> bool:
    try:
        headers = {"User-Agent": f"AirGap/{config.VERSION}"}
        req = urllib.request.Request(url, headers=headers)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with (
            urllib.request.urlopen(req, timeout=config.UPDATE_CHECK_TIMEOUT) as resp,
            open(dest_path, "wb") as f,
        ):
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


def download_checksums(tag_name: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"AirGap/{config.VERSION}",
    }
    base = f"{config.GITHUB_API_BASE}/repos/{config.GITHUB_OWNER}/{config.GITHUB_REPO}"
    url = f"{base}/releases/tags/{tag_name}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=config.UPDATE_CHECK_TIMEOUT) as resp:
            release = json.loads(resp.read().decode("utf-8"))

        for asset in release.get("assets", []):
            if asset["name"] == "SHA256SUMS":
                checksum_url = asset["browser_download_url"]
                req = urllib.request.Request(checksum_url, headers=headers)
                with urllib.request.urlopen(req, timeout=config.UPDATE_CHECK_TIMEOUT) as resp:
                    text = resp.read().decode("utf-8")
                checksums = {}
                for line in text.strip().splitlines():
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        checksums[parts[1].strip()] = parts[0].strip()
                return checksums
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        pass
    return {}
