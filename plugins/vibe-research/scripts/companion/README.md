# Research companion implementations

`../companion.py` is the only public launcher. It owns workspace identity, the workbench URL, PID/state files and these commands:

- default: ensure one collapsed companion exists;
- `--check`: report whether the current host can show it;
- `--status`: return current platform and visible state;
- `--toggle`: use the same expand/collapse path as a click;
- `--stop`: close the companion.

Platform UI code stays isolated:

- `macos/main.m`: AppKit and WebKit;
- `windows/`: WinForms and WebView2, built for `win-x64` and `win-arm64`;
- `linux/main.py`: GTK 3 and WebKitGTK 4.1/4.0.

All implementations keep a 62 × 62 draggable button and a separate workbench window of at most 1120 × 780. The workbench is sized from its own native window, so Codex sidebar changes cannot shift its web viewport. Button position and the shared UI-state keys persist locally. The companion never writes research graph data directly.

Each workspace also holds an exclusive native instance lock. The macOS launcher retires the earlier raw `vr-companion` helper during migration, preventing an untracked legacy button from appearing beside the current companion.

Windows release binaries belong in `windows/publish/<rid>/`. GitHub Actions populates those folders while building a release archive; they are deliberately absent from the source tree. Linux system packages are not vendored. A host that fails preflight keeps the browser workbench path available.

Before release, run the native acceptance checklist on each OS: install, first project conversation, single-instance check, drag and relaunch position recovery, click to expand, Codex sidebar toggle followed by reopen, workbench navigation, collapse, task continuation, right-click exit and browser fallback.
