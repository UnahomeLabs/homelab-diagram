#!/usr/bin/env python3
"""Download the service icons used by build_unahome.py into icons/.

Same source as the upstream fetch_icons.py (homarr-labs/dashboard-icons via
jsDelivr, raw GitHub as fallback), with a PNG fallback: a handful of services
only ship a raster icon. Missing icons are not fatal - build_unahome.py draws a
lettered placeholder instead.
"""
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
ICONS = ROOT / "icons"
SOURCES = [
    "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/{ext}/{name}.{ext}",
    "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/{ext}/{name}.{ext}",
]

ICON_MAP = {
    "adguard": "adguard-home",
    "bentopdf": "bentopdf",
    "bookorbit": "bookorbit",
    "caddy": "caddy",
    "cloudflare": "cloudflare",
    "docker": "docker",
    "firecrawl": "firecrawl",
    "firefly": "firefly-iii",
    "ghostfolio": "ghostfolio",
    "glance": "glance",
    "grafana": "grafana",
    "homeassistant": "home-assistant",
    "homepage": "homepage",
    "hortusfox": "hortusfox",
    "influxdb": "influxdb",
    "kiwix": "kiwix",
    "langfuse": "langfuse",
    "leantime": "leantime",
    "litellm": "litellm",
    "n8n": "n8n",
    "ntfy": "ntfy",
    "pihole": "pi-hole",
    "postgresql": "postgresql",
    "proxmox": "proxmox",
    "stalwart": "stalwart",
    "tandoor": "tandoor-recipes",
    "tailscale": "tailscale",
    "trilium": "trilium",
    "truenas": "truenas-scale",
    "unifi": "unifi",
    "vaultwarden": "vaultwarden",
    "wanderer": "wanderer",
    "windows": "microsoft-windows",
    "windmill": "windmill",
}
# dark logos: recolour for the dark canvas
RECOLOR = {
    "openwebui-l": ("open-webui-light", None, None),
    "ollama-l": ("ollama", 'fill="black"', 'fill="#e6edf3"'),
}


def fetch(remote, tries=3):
    """(ext, bytes) for the first format this service actually ships."""
    for ext in ("svg", "png"):
        for url_tpl in SOURCES:
            url = url_tpl.format(ext=ext, name=remote)
            req = urllib.request.Request(url, headers={"User-Agent": "homelab-diagram/1.0"})
            for attempt in range(tries):
                try:
                    with urllib.request.urlopen(req, timeout=20) as r:
                        return ext, r.read()
                except Exception as e:                       # noqa: BLE001
                    if getattr(e, "code", None) in (403, 404):
                        break
                    if attempt == tries - 1:
                        break
                    time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{remote}: no svg or png available")


def already(local):
    return any((ICONS / f"{local}.{e}").exists() for e in ("svg", "png"))


def main():
    ICONS.mkdir(exist_ok=True)
    failed = []
    for local, remote in ICON_MAP.items():
        if already(local):
            continue
        time.sleep(0.15)
        try:
            ext, blob = fetch(remote)
            (ICONS / f"{local}.{ext}").write_bytes(blob)
        except Exception as e:                               # noqa: BLE001
            failed.append(f"{local} ({remote}): {e}")
    for local, (remote, old, new) in RECOLOR.items():
        if already(local):
            continue
        try:
            ext, blob = fetch(remote)
            if ext == "svg" and old:
                blob = blob.replace(old.encode(), new.encode())
            (ICONS / f"{local}.{ext}").write_bytes(blob)
        except Exception as e:                               # noqa: BLE001
            failed.append(f"{local} ({remote}): {e}")

    have = len(list(ICONS.glob("*.svg"))) + len(list(ICONS.glob("*.png")))
    print(f"icons on disk: {have}")
    if failed:
        print("not available (lettered placeholder will be drawn):\n  " + "\n  ".join(failed))


if __name__ == "__main__":
    main()
