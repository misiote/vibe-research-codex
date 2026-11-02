#!/bin/sh
# Maintainer-only build. End users run the packaged universal binary.
set -eu
vr_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
vr_macos="$vr_root/plugins/vibe-research/scripts/companion/macos"
mkdir -p "$vr_macos/prebuilt"
clang "$vr_macos/main.m" -arch arm64 -arch x86_64 -mmacosx-version-min=12.0 -O -fobjc-arc -framework Cocoa -framework QuartzCore -framework WebKit -o "$vr_macos/prebuilt/VibeResearchCompanion"
codesign --force --sign - "$vr_macos/prebuilt/VibeResearchCompanion"
lipo "$vr_macos/prebuilt/VibeResearchCompanion" -verify_arch arm64 x86_64
codesign --verify --strict "$vr_macos/prebuilt/VibeResearchCompanion"
python3 - "$vr_macos" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
manifest={'architectures':['arm64','x86_64'],'minimum_macos':'12.0','signing':'ad-hoc; not Developer ID notarized','source_sha256':hashlib.sha256((root/'main.m').read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256((root/'prebuilt/VibeResearchCompanion').read_bytes()).hexdigest()}
(root/'prebuilt/build.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
