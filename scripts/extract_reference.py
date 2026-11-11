"""Extract user-supplied fonts/imagery without executing the reference runtime."""

import base64
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def script(document, kind):
    match = re.search(r'<script type="__bundler/' + kind + r'">(.*?)</script>', document, re.S)
    if not match:
        raise ValueError(f"Missing reference bundle {kind}")
    return json.loads(match.group(1))


def decode(asset):
    data = base64.b64decode(asset["data"])
    return gzip.decompress(data) if asset.get("compressed") else data


def main():
    reference = (ROOT / "Understory.html").read_text()
    pages = script(reference, "manifest")
    order = script(reference, "page_order")
    landing = decode(pages[order[0]]).decode()
    assets = script(landing, "manifest")
    template = script(landing, "template")
    output = ROOT / "frontend/public/assets"
    output.mkdir(parents=True, exist_ok=True)
    for css in re.findall(r"@font-face\s*\{(.*?)\}", template, re.S):
        family = re.search(r"font-family:\s*'([^']+)'", css)
        source = re.search(r'url\("([^"/]+)"\)', css)
        if not family or not source or source[1] not in assets:
            continue
        italic = "font-style: italic" in css
        filename = {
            "Instrument Serif": "instrument-serif-italic.woff2" if italic else "instrument-serif.woff2",
            "Inter": "inter.woff2",
            "JetBrains Mono": "jetbrains-mono.woff2",
        }[family[1]]
        (output / filename).write_bytes(decode(assets[source[1]]))
    for asset in assets.values():
        if asset["mime"] == "image/jpeg":
            (output / "meadow.jpg").write_bytes(decode(asset))
            break
    print("Extracted supplied meadow image and four font files; reference HTML unchanged.")


if __name__ == "__main__":
    main()
