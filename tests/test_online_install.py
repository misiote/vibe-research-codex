"""Bootstrap install, update, failure and archive-boundary regressions."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap', ROOT / 'scripts/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)
SHA = 'a' * 40


def archive(extra=None):
    files = {'install.sh': b'#!/bin/sh\n', 'install.ps1': b'# fixture\n', '.agents/plugins/marketplace.json': b'{}',
             'plugins/vibe-research/scripts/install_modes.py': b'# fixture\n'}
    files['plugins/vibe-research/SHA256SUMS.json'] = json.dumps({'scripts/install_modes.py': hashlib.sha256(files['plugins/vibe-research/scripts/install_modes.py']).hexdigest()}).encode()
    files.update(extra or {})
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.comment = SHA.encode()
        for name, data in files.items():
            z.writestr(zipfile.ZipInfo(name if name.startswith('/') else 'repo-' + SHA + '/' + name), data)
    return out.getvalue()


class OnlineInstall(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def install(self, payload=None, runner=None):
        content = archive() if payload is None else payload
        with patch.object(bootstrap, 'preflight'), patch.object(bootstrap, 'prepare_marketplace', return_value=None), patch.object(bootstrap, 'fetch', return_value=content) as download, patch.object(bootstrap.subprocess, 'run', side_effect=runner, return_value=subprocess.CompletedProcess([], 0)) as run:
            result = bootstrap.install(self.root / 'install', self.root / 'research')
        return result, download, run

    def test_direct_download_records_archive_commit_without_api(self):
        result, download, run = self.install()
        self.assertEqual(download.call_args_list[0].args[0], 'https://codeload.github.com/' + bootstrap.REPOSITORY + '/zip/main')
        self.assertEqual(result['aliases'], 'installed')
        self.assertEqual(download.call_count, 1)
        self.assertEqual(result['commit'], SHA)
        self.assertEqual(result['archive_sha256'], hashlib.sha256(archive()).hexdigest())
        self.assertTrue(Path(result['source']).is_dir())
        self.assertEqual(run.call_args_list[0].kwargs['env']['VIBE_RESEARCH_WORKSPACE'], str(self.root / 'research'))
        self.assertIn('--install', run.call_args_list[1].args[0])
        self.assertFalse((self.root / 'install/.install-lock').exists())
        self.assertTrue((self.root / 'install/installed.json').is_file())

    def test_api_rate_limit_is_irrelevant_to_direct_install(self):
        def fetch(url):
            if 'api.github.com' in url:
                raise AssertionError('Installer must never contact the rate-limited REST API')
            return archive()
        with patch.object(bootstrap, 'preflight'), patch.object(bootstrap, 'prepare_marketplace', return_value=None), patch.object(bootstrap, 'fetch', side_effect=fetch) as download, patch.object(bootstrap.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            result = bootstrap.install(self.root / 'install', self.root / 'research')
        self.assertEqual(download.call_count, 1)
        self.assertEqual(result['commit'], SHA)

    def test_archive_without_commit_uses_content_digest_not_fake_commit(self):
        out = io.BytesIO(archive())
        with zipfile.ZipFile(out, 'a') as z:
            z.comment = b''
        result, _, _ = self.install(out.getvalue())
        self.assertIsNone(result['commit'])
        self.assertEqual(Path(result['source']).name, 'archive-' + hashlib.sha256(out.getvalue()).hexdigest())

    def test_explicit_commit_must_match_archive_metadata(self):
        with patch.object(bootstrap, 'preflight'), patch.object(bootstrap, 'fetch', return_value=archive()), patch.object(bootstrap.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, '提交与指定版本不一致'):
                bootstrap.install(self.root / 'install', self.root / 'research', ref='b' * 40)
            run.assert_not_called()

    def test_http_403_falls_back_to_ssh_and_records_transport(self):
        failure = urllib.error.HTTPError('https://codeload.github.com/fixture', 403, 'rate limit exceeded', {}, None)
        with patch.object(bootstrap, 'preflight'), patch.object(bootstrap, 'prepare_marketplace', return_value=None), patch.object(bootstrap, 'fetch', side_effect=failure), patch.object(bootstrap, 'fetch_ssh', return_value=archive()) as ssh, patch.object(bootstrap.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            result = bootstrap.install(self.root / 'install', self.root / 'research')
        ssh.assert_called_once_with('main')
        self.assertEqual(result['transport'], 'ssh')
        self.assertEqual(result['commit'], SHA)

    def test_https_success_never_attempts_ssh(self):
        with patch.object(bootstrap, 'fetch', return_value=archive()), patch.object(bootstrap, 'fetch_ssh') as ssh:
            _, transport = bootstrap.download_snapshot('main')
        self.assertEqual(transport, 'https')
        ssh.assert_not_called()

    def test_both_download_failures_show_both_causes(self):
        with patch.object(bootstrap, 'fetch', side_effect=OSError('HTTP fixture unavailable')), patch.object(bootstrap, 'fetch_ssh', side_effect=ValueError('SSH fixture unavailable')):
            with self.assertRaises(ValueError) as failure:
                bootstrap.download_snapshot('main')
        self.assertIn('HTTP fixture unavailable', str(failure.exception))
        self.assertIn('SSH fixture unavailable', str(failure.exception))

    def test_ssh_uses_existing_keys_and_strict_noninteractive_options(self):
        def run(command, **kwargs):
            if 'archive' in command:
                kwargs['stdout'].write(archive())
            return subprocess.CompletedProcess(command, 0)
        with patch.object(bootstrap.shutil, 'which', side_effect=lambda name: name), patch.object(bootstrap.subprocess, 'run', side_effect=run) as command:
            self.assertEqual(bootstrap.fetch_ssh('main'), archive())
        fetch = next(c for c in command.call_args_list if 'fetch' in c.args[0])
        self.assertEqual(fetch.args[0][-2:], ['origin', 'main'])
        ssh = fetch.kwargs['env']['GIT_SSH_COMMAND']
        self.assertIn('BatchMode=yes', ssh)
        self.assertIn('StrictHostKeyChecking=yes', ssh)
        self.assertEqual(fetch.kwargs['env']['GIT_TERMINAL_PROMPT'], '0')
        self.assertEqual(fetch.kwargs['timeout'], 120)
        self.assertFalse((self.root / '.ssh').exists())

    def test_ssh_does_not_accept_option_as_ref(self):
        with patch.object(bootstrap.shutil, 'which', return_value='git'), patch.object(bootstrap.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                bootstrap.fetch_ssh('--upload-pack=invalid')
            run.assert_not_called()

    def test_checksum_failure_does_not_trigger_ssh(self):
        with patch.object(bootstrap, 'fetch_ssh') as ssh:
            with self.assertRaisesRegex(ValueError, '校验失败'):
                self.install(archive({'plugins/vibe-research/scripts/install_modes.py': b'changed'}))
        ssh.assert_not_called()

    def test_repeat_install_keeps_research_and_reuses_snapshot(self):
        first, _, _ = self.install()
        research = self.root / 'research'
        research.mkdir()
        (research / 'keep').write_text('user data')
        second, _, _ = self.install()
        self.assertEqual(first['source'], second['source'])
        self.assertEqual((research / 'keep').read_text(), 'user data')

    def test_modified_installation_is_not_overwritten(self):
        first, _, _ = self.install()
        p = Path(first['source']) / 'install.sh'
        p.write_text('user edits')
        with self.assertRaisesRegex(ValueError, '--install-dir'):
            self.install()
        self.assertEqual(p.read_text(), 'user edits')
        self.assertFalse((self.root / 'install/.install-lock').exists())

    def test_failed_plugin_install_has_no_success_receipt(self):
        def fail(*args, **kwargs):
            raise subprocess.CalledProcessError(1, args[0])
        with self.assertRaises(subprocess.CalledProcessError):
            self.install(runner=fail)
        self.assertFalse((self.root / 'install/installed.json').exists())
        self.assertFalse((self.root / 'install/.install-lock').exists())

    def test_alias_conflict_does_not_hide_successful_plugin_install(self):
        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0 if kwargs.get('check') else 1)
        result, _, _ = self.install(runner=run)
        self.assertEqual(result['aliases'], 'conflict')

    def test_checksum_failure_prevents_execution(self):
        with self.assertRaisesRegex(ValueError, '校验失败'):
            self.install(archive({'plugins/vibe-research/scripts/install_modes.py': b'changed'}))
        self.assertFalse((self.root / 'install/installed.json').exists())

    def test_unsafe_archive_paths_are_rejected_before_extraction(self):
        for path in ['../outside', '/absolute', 'nested/../../outside', 'a\\b', 'C:/file']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                bootstrap.unpack(archive({path: b'bad'}), self.root / 'unpack')
        self.assertFalse((self.root / 'outside').exists())

    def test_symlink_is_rejected(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            member = zipfile.ZipInfo('root/link')
            member.create_system = 3
            member.external_attr = 0o120777 << 16
            z.writestr(member, 'target')
        with self.assertRaises(ValueError):
            bootstrap.unpack(out.getvalue(), self.root / 'unpack')

    def test_marketplace_rebind_only_accepts_own_single_plugin_source(self):
        old = self.root / 'old'
        (old / '.agents/plugins').mkdir(parents=True)
        manifest = old / 'plugins/vibe-research/.codex-plugin/plugin.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'repository': 'https://github.com/' + bootstrap.REPOSITORY}))
        catalog = old / '.agents/plugins/marketplace.json'
        catalog.write_text(json.dumps({'plugins': [{'name': 'vibe-research'}]}))
        listing = json.dumps({'marketplaces': [{'name': 'vibe-research-local', 'root': str(old)}]}).encode()
        with patch.object(bootstrap.subprocess, 'check_output', return_value=listing), patch.object(bootstrap.subprocess, 'run') as run:
            self.assertEqual(bootstrap.prepare_marketplace('codex', self.root / 'new'), old)
            run.assert_called_once_with(['codex', 'plugin', 'marketplace', 'remove', 'vibe-research-local'], check=True)
        catalog.write_text(json.dumps({'plugins': [{'name': 'vibe-research'}, {'name': 'another-plugin'}]}))
        with patch.object(bootstrap.subprocess, 'check_output', return_value=listing), patch.object(bootstrap.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                bootstrap.prepare_marketplace('codex', self.root / 'new')
            run.assert_not_called()

    def test_stale_download_source_is_removed_before_listing_again(self):
        missing = self.root / 'deleted-download'
        error = ('Error: failed to load marketplace(s):\n- `vibe-research-local` at ' + str(missing) + ': marketplace root does not contain a supported manifest\n').encode()
        failure = subprocess.CalledProcessError(1, 'codex', stderr=error)
        with patch.object(bootstrap.subprocess, 'check_output', side_effect=[failure, b'{"marketplaces": []}']) as listing, patch.object(bootstrap.subprocess, 'run') as run:
            self.assertIsNone(bootstrap.prepare_marketplace('codex', self.root / 'new'))
            self.assertEqual(listing.call_count, 2)
            run.assert_called_once_with(['codex', 'plugin', 'marketplace', 'remove', 'vibe-research-local'], check=True)

    def test_existing_manifest_is_never_removed_by_stale_source_repair(self):
        old = self.root / 'existing'
        manifest = old / '.agents/plugins/marketplace.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{invalid user config')
        error = ('- `vibe-research-local` at ' + str(old) + ': marketplace root does not contain a supported manifest').encode()
        with patch.object(bootstrap.subprocess, 'check_output', side_effect=subprocess.CalledProcessError(1, 'codex', stderr=error)), patch.object(bootstrap.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                bootstrap.prepare_marketplace('codex', self.root / 'new')
            run.assert_not_called()
        self.assertEqual(manifest.read_text(), '{invalid user config')

    def test_other_broken_marketplace_does_not_trigger_removal(self):
        error = b'- `another-marketplace` at /missing: marketplace root does not contain a supported manifest'
        with patch.object(bootstrap.subprocess, 'check_output', side_effect=subprocess.CalledProcessError(1, 'codex', stderr=error)), patch.object(bootstrap.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                bootstrap.prepare_marketplace('codex', self.root / 'new')
            run.assert_not_called()

    def test_failed_stale_source_removal_stops_repair(self):
        error = ('- `vibe-research-local` at ' + str(self.root / 'missing') + ': marketplace root does not contain a supported manifest').encode()
        with patch.object(bootstrap.subprocess, 'check_output', side_effect=subprocess.CalledProcessError(1, 'list', stderr=error)) as listing, patch.object(bootstrap.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'remove')):
            with self.assertRaises(subprocess.CalledProcessError):
                bootstrap.prepare_marketplace('codex', self.root / 'new')
            self.assertEqual(listing.call_count, 1)

    def test_failed_update_restores_previous_marketplace_registration(self):
        previous = self.root / 'previous'
        with patch.object(bootstrap, 'preflight', return_value='codex'), patch.object(bootstrap, 'prepare_marketplace', return_value=previous), patch.object(bootstrap, 'fetch', return_value=archive()), patch.object(bootstrap.subprocess, 'run', side_effect=[subprocess.CalledProcessError(1, 'installer'), subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0)]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                bootstrap.install(self.root / 'install', self.root / 'research')
        self.assertEqual(run.call_args_list[-1].args[0], ['codex', 'plugin', 'marketplace', 'add', str(previous)])
        self.assertFalse((self.root / 'install/installed.json').exists())

    @unittest.skipIf(os.name == 'nt', 'POSIX shell entry')
    def test_partial_bootstrap_download_is_never_executed(self):
        tools = self.root / 'tools'
        tools.mkdir()
        python = tools / 'python3'
        python.write_text('#!' + sys.executable + '\nimport sys,os\nif len(sys.argv)>3:\n open(sys.argv[-1],"w").write(' + repr('raise RuntimeError("PARTIAL_RESPONSE_EXECUTED")') + ');raise SystemExit(22)\nos.execv(' + repr(sys.executable) + ', [' + repr(sys.executable) + ']+sys.argv[1:])\n')
        python.chmod(0o755)
        result = subprocess.run(['sh', str(ROOT / 'install-online.sh')], env=dict(os.environ, VIBE_RESEARCH_PYTHON=str(python), PATH=str(tools) + os.pathsep + os.environ['PATH']), capture_output=True, text=True)
        self.assertEqual(result.returncode, 22)
        self.assertNotIn('PARTIAL_RESPONSE_EXECUTED', result.stderr)

    def test_concurrent_install_is_rejected(self):
        (self.root / 'install/.install-lock').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, '已有安装'):
            self.install()


if __name__ == '__main__':
    unittest.main()
