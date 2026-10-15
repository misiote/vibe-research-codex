"""Offline regressions for Windows fixes and unchanged macOS/Linux behavior."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import uuid
import zipfile

PLUGIN = Path(__file__).resolve().parents[1] / 'plugins/vibe-research'
sys.path.insert(0, str(PLUGIN / 'runtime'))
from vr import backup, connections, hub, literature, request_gate, resources, watch
from vr.store import ResearchError, Store


def script(name):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlatformCompatibility(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='vibe-中文 空格-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def project(self):
        root = self.root / '研究项目'
        store = Store.init(root, '中文研究问题')
        store.db.close()
        return root

    def test_unicode_registry_and_idempotent_creation(self):
        registry = self.root / 'projects.json'
        request = str(uuid.uuid4())
        first = hub.create(registry, '中文项目', '中文问题', ['crossref'], request)
        second = hub.create(registry, '中文项目', '中文问题', ['crossref'], request)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(hub.entries(registry)[0]['name'], '中文项目')

    def test_bundle_round_trip_has_portable_nonempty_paths(self):
        project = self.project()
        destination = self.root / '备份.zip'
        self.assertGreater(backup.create(project, destination)['files'], 0)
        with zipfile.ZipFile(destination) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertIn('.research/research.db', manifest['files'])
            self.assertTrue(all('\\' not in name for name in archive.namelist()))
        restored = self.root / '恢复'
        backup.restore(destination, restored)
        store = Store(restored)
        try:
            self.assertTrue(store.doctor()['ok'])
            self.assertEqual(store.rows('nodes')[0]['title'], '中文研究问题')
        finally:
            store.db.close()

    def test_file_credentials_do_not_require_posix_fchmod_on_windows(self):
        path = self.root / 'credentials.json'
        with patch.object(connections, 'credential_path', return_value=path):
            connections.save('s2', 'test-only-dummy-value', backend='file')
            self.assertEqual(connections.read_saved(), {'s2': 'test-only-dummy-value'})
        if os.name != 'nt':
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_budget_default_preserves_posix_location(self):
        fake_os = SimpleNamespace(name='posix', environ={})
        with patch.object(request_gate, 'os', fake_os):
            self.assertEqual(request_gate.location(), Path.home() / '.config/vibe-research/request-budget.sqlite3')

    def test_budget_windows_location_and_override(self):
        fake_os = SimpleNamespace(name='nt', environ={'APPDATA': str(self.root)})
        with patch.object(request_gate, 'os', fake_os):
            self.assertEqual(request_gate.location(), self.root / 'VibeResearch/runtime/request-budget.sqlite3')
            fake_os.environ['VR_RUNTIME_DIR'] = str(self.root / 'custom')
            self.assertEqual(request_gate.location(), self.root / 'custom/request-budget.sqlite3')

    def test_budget_local_failure_is_actionable(self):
        with patch.object(request_gate, 'location', return_value=self.root / 'budget.sqlite3'), patch.object(sqlite3, 'connect', side_effect=sqlite3.OperationalError('unwritable')):
            with self.assertRaisesRegex(ResearchError, 'VR_RUNTIME_DIR'):
                request_gate.connect()

    def test_crossref_sort_is_scoped_to_windows(self):
        for system in ('nt', 'posix'):
            with self.subTest(system=system):
                router = SimpleNamespace(request=lambda *args: (json.dumps({'message': {'items': [], 'total-results': 0}}).encode(), {}))
                with patch.object(router, 'request', wraps=router.request) as call, patch.object(literature, 'os', SimpleNamespace(name=system)):
                    literature.search_page(router, 'query', 'crossref')
                expected = {'query': 'query', 'rows': 25, 'cursor': '*'}
                if system == 'nt':
                    expected.update(sort='score', order='desc')
                self.assertEqual(call.call_args.args[2], expected)

    def test_pdf_links_preserve_native_viewer_on_other_platforms(self):
        attachment = {'path': 'test.pdf', 'sha256': 'a' * 64, 'name': '论文.pdf'}
        store = SimpleNamespace()
        for platform in ('win32', 'darwin', 'linux'):
            with self.subTest(platform=platform), patch.object(resources, 'sys', SimpleNamespace(platform=platform)), patch.object(resources, 'files', return_value=[attachment]):
                links = resources.links(store, {'id': 'P0001', 'kind': 'P', 'title': '论文', 'data': {}})
                file_link = next(link for link in links if link['kind'] == 'file')
                self.assertEqual(file_link['url'], ('/pdf/' if platform == 'win32' else '/file/') + 'a' * 64)

    def test_http_platform_defaults_and_static_boundaries(self):
        for platform in ('win32', 'darwin', 'linux'):
            with self.subTest(platform=platform), patch.object(watch, 'sys', SimpleNamespace(platform=platform, executable=sys.executable)):
                server = watch.server(self.root, 0, self.root / 'projects.json')
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base = 'http://127.0.0.1:' + str(server.server_port)
                    with urllib.request.urlopen(base) as response:
                        body = response.read().decode('utf8')
                        policy = response.headers['Content-Security-Policy']
                    source = 'openalex' if platform == 'win32' else 'core'
                    self.assertIn("box.checked=['arxiv','crossref','" + source + "']", body)
                    self.assertEqual('wasm-unsafe-eval' in policy, platform == 'win32')
                    if platform == 'win32':
                        with urllib.request.urlopen(base + '/static/pdfjs/pdf.mjs') as response:
                            self.assertEqual(response.headers.get_content_type(), 'application/javascript')
                        for route in ('/static/../../store.py', '/static/pdfjs/not-found'):
                            with self.assertRaises(urllib.error.HTTPError) as error:
                                urllib.request.urlopen(base + route)
                            self.assertEqual(error.exception.code, 404)
                    else:
                        with self.assertRaises(urllib.error.HTTPError):
                            urllib.request.urlopen(base + '/static/pdfjs/pdf.mjs')
                finally:
                    server.shutdown()
                    thread.join()
                    server.server_close()

    def test_installer_keeps_project_configuration_and_unicode_launchers(self):
        workspace = self.root / '工作区'
        args = [sys.executable, '-X', 'utf8', str(PLUGIN / 'scripts/install_cli.py'), '--workspace', str(workspace), '--bin-dir', str(self.root / '命令'), '--config-dir', str(self.root / '设置')]
        data = json.loads(subprocess.check_output(args).decode('utf8'))
        config = workspace / '.codex/config.toml'
        self.assertTrue(data['project_config_created'])
        config.write_text('# user-owned settings\n', encoding='utf8')
        data = json.loads(subprocess.check_output(args).decode('utf8'))
        self.assertFalse(data['project_config_created'])
        self.assertEqual(config.read_text(encoding='utf8'), '# user-owned settings\n')
        settings = subprocess.check_output([sys.executable, '-X', 'utf8', str(self.root / '命令/vr-workbench.py'), '--show-config'])
        self.assertEqual(json.loads(settings.decode('utf8'))['workspace'], str(workspace))
        if os.name == 'nt':
            for name in ('vr', 'vr-workbench', 'vr-companion'):
                self.assertIn('-X utf8', (self.root / '命令' / (name + '.cmd')).read_text(encoding='utf8'))

    def test_windows_sdk_check_requires_an_sdk(self):
        companion = script('companion')
        with patch.object(companion.shutil, 'which', return_value='dotnet'):
            for output, expected in (('', False), ('6.0.400 [sdk]', False), ('8.0.426 [sdk]', True), ('9.0.100 [sdk]', True)):
                with self.subTest(output=output), patch.object(companion, 'run', return_value=SimpleNamespace(returncode=0, stdout=output)):
                    self.assertEqual(companion.windows_sdk_ready(), expected)


if __name__ == '__main__':
    unittest.main()
