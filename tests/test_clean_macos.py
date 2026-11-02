"""No-compiler runtime/launcher contracts for the macOS distribution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/vibe-research'


def load(name):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CleanMacOS(unittest.TestCase):
    def test_packaged_companion_readiness_never_probes_clang(self):
        module = load('companion')
        with patch.object(module.shutil, 'which', side_effect=AssertionError('Compiler lookup on clean Mac')):
            result = module.check_host(PLUGIN, 'macos')
        self.assertTrue(result['ok'])
        self.assertIn('prebuilt', result['entry'])

    def test_apple_clang_stub_is_not_a_ready_compiler(self):
        module = load('companion')
        with patch.object(module, 'macos_packaged_binary', return_value=None), patch.object(module.shutil, 'which', return_value='/usr/bin/clang'), patch.object(module, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertFalse(module.check_host(PLUGIN, 'macos')['ok'])
        run.assert_called_once_with(['/usr/bin/xcode-select', '-p'])

    def test_app_bundle_is_created_by_copy_without_compilation(self):
        module = load('companion')
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'run', side_effect=AssertionError('Compiler executed')):
            app = Path(temp) / 'Companion.app'
            module.build_macos_app(PLUGIN / 'scripts/companion/macos/main.m', app)
            binary = app / 'Contents/MacOS/VibeResearchCompanion'
            self.assertEqual(binary.read_bytes(), module.macos_packaged_binary(PLUGIN).read_bytes())
            self.assertTrue(binary.stat().st_mode & 0o111)
            self.assertTrue((app / 'Contents/Info.plist').is_file())

    def test_modified_binary_is_not_accepted(self):
        module = load('companion')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mac = root / 'scripts/companion/macos'
            (mac / 'prebuilt').mkdir(parents=True)
            (mac / 'main.m').write_bytes(b'source')
            (mac / 'prebuilt/VibeResearchCompanion').write_bytes(b'tampered')
            (mac / 'prebuilt/build.json').write_text(json.dumps({'source_sha256': hashlib.sha256(b'source').hexdigest(), 'binary_sha256': hashlib.sha256(b'original').hexdigest()}))
            self.assertIsNone(module.macos_packaged_binary(root))

    def test_installed_launcher_records_exact_python_and_runs_without_path_lookup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run([sys.executable, str(PLUGIN / 'scripts/install_cli.py'), '--workspace', str(root / 'workspace'), '--bin-dir', str(root / 'bin'), '--config-dir', str(root / 'config')], check=True, capture_output=True)
            data = json.loads((root / 'config/launcher.json').read_text())
            self.assertEqual(data['python'], str(Path(sys.executable).resolve()))
            if sys.platform != 'win32':
                result = subprocess.run([str(root / 'bin/vr-workbench'), '--show-config'], env={'PATH': '/nonexistent'}, capture_output=True, check=True)
                self.assertEqual(json.loads(result.stdout)['workspace'], str((root / 'workspace').resolve()))

    def test_aliases_respect_codex_home(self):
        module = load('install_modes')
        with tempfile.TemporaryDirectory() as temp:
            result = module.install(PLUGIN, Path(temp) / 'skills', True)
            skill = (Path(result['skills_dir']) / 'vrpet/SKILL.md').read_text()
            self.assertIn('launcher.json', skill)
            self.assertIn('python', skill)


if __name__ == '__main__':
    unittest.main()
