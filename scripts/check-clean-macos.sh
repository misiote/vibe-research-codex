#!/bin/sh
# Maintainer/CI test: system tools only; no user settings or plugin registration.
set -eu
vr_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
vr_test=$(mktemp -d "${TMPDIR:-/tmp}/vibe-clean-macos.XXXXXXXX")
trap 'rm -rf "$vr_test"' EXIT HUP INT TERM
mkdir "$vr_test/tools"
for vr_name in python python3 git clang; do
  printf '#!/bin/sh\necho "Unexpected preinstalled dependency: %s" >&2\nexit 97\n' "$vr_name" > "$vr_test/tools/$vr_name"
  chmod +x "$vr_test/tools/$vr_name"
done
awk '/^vr_bootstrap=/{exit} {print}' "$vr_root/install-online.sh" > "$vr_test/check.sh"
cat >> "$vr_test/check.sh" <<'CHECK'
"$vr_python" -I -c 'import sys,ssl,sqlite3,ctypes,venv; assert sys.version_info[:2] == (3,12)'
"$vr_python" -I -m pip --isolated install --disable-pip-version-check --no-index --no-deps "$VR_CLEAN_SOURCE/plugins/vibe-research/vendor/pypdf-6.21.4-py3-none-any.whl"
"$vr_python" -I -c 'from pypdf import PdfReader,PdfWriter; import io; b=io.BytesIO(); w=PdfWriter(); w.add_blank_page(width=100,height=100); w.write(b); b.seek(0); assert len(PdfReader(b).pages)==1'
"$vr_python" "$VR_CLEAN_SOURCE/plugins/vibe-research/scripts/companion.py" --workspace "$VIBE_RESEARCH_RUNTIME_DIR/workspace" --check
printf 'Clean PATH, private Python, offline PDF, prebuilt companion: PASS\n'
CHECK
unset VIBE_RESEARCH_PYTHON VIBE_RESEARCH_MANAGED_PYTHON
PATH="$vr_test/tools:/usr/bin:/bin:/usr/sbin:/sbin" VIBE_RESEARCH_RUNTIME_DIR="$vr_test/runtimes" VR_CLEAN_SOURCE="$vr_root" sh "$vr_test/check.sh"
