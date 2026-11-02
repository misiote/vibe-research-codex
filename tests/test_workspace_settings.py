"""Workspace settings never require a research project or persist credentials."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import threading
import urllib.request
import urllib.error
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugins/vibe-research/runtime'))
from vr import workspace_config, brainstorm, bridge

class WorkspaceSettings(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_local_status_does_not_claim_unverified_connections_are_available(self):
        providers=[{'provider':'wos','configured':False},{'provider':'arxiv','configured':True}]
        with patch.object(workspace_config.connections,'status',return_value={'providers':providers}),patch.object(workspace_config.integrations,'runtime_status',return_value={'pypdf':True}):
            data=workspace_config.snapshot(self.root)
        self.assertEqual([p['status'] for p in data['providers']],['needs_auth','unverified'])
        self.assertFalse(self.root.joinpath('.research').exists())
        self.assertFalse(self.root.joinpath('.vibe-research').exists())
    def test_check_cache_keeps_only_status_and_time_and_invalidation_is_scoped(self):
        workspace_config.record(self.root,{'checked_at':'2026-11-02','providers':[{'provider':'wos','status':'blocked','message':'secret-fixture','headers':{'Authorization':'secret-fixture'}},{'provider':'arxiv','status':'passed'}]})
        text=workspace_config.path(self.root).read_text()
        self.assertNotIn('secret-fixture',text)
        workspace_config.invalidate(self.root,'wos')
        self.assertEqual(list(workspace_config.load(self.root)),['arxiv'])
        self.assertFalse((self.root/'.research').exists())
    def test_actual_probe_is_only_run_by_explicit_check(self):
        result={'checked_at':'now','providers':[{'provider':'arxiv','status':'passed'}]}
        with patch.object(workspace_config.integrations,'preflight',return_value=result) as preflight:
            self.assertEqual(workspace_config.check(self.root,['arxiv']),result)
            preflight.assert_called_once_with(['arxiv'])
        self.assertEqual(workspace_config.load(self.root)['arxiv']['status'],'passed')
    def test_new_notes_can_feed_transfer_without_old_direction_forms(self):
        board=brainstorm.write(self.root,topic='Test notes')
        board=brainstorm.write(self.root,board['id'],module='notes',content='A minimal falsifiable idea')
        self.assertEqual(brainstorm.handoff(self.root,board['id'])['notes']['content'],'A minimal falsifiable idea')
        self.assertEqual(brainstorm.packet(self.root,board['id'],'notes')['skill'],'vibe-research')
        self.assertNotIn('directions',board['modules'])
        result=bridge.preview(self.root,{'direction':'promote','board':board['id'],'name':'Prototype','branch':'engineering/test'})
        self.assertIn('A minimal falsifiable idea',json.dumps(result))

class SettingsHTTP(unittest.TestCase):
    def setUp(self):
        from vr import watch
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.server=watch.server(self.root,0,self.root/'projects.json')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.thread.join();self.server.server_close()
    def test_global_settings_do_not_require_any_project(self):
        with urllib.request.urlopen(self.base+'/settings') as response:
            self.assertIn('所有项目共用',response.read().decode())
        with urllib.request.urlopen(self.base+'/api/settings') as response:
            data=json.load(response)
        self.assertEqual(data['scope'],'workspace')
        self.assertNotIn('value',data['providers'][0])
        self.assertFalse((self.root/'.research').exists())
    def test_global_configuration_rejects_foreign_origin_even_with_session_token(self):
        with urllib.request.urlopen(self.base+'/api/session') as response:
            token=json.load(response)['token']
        body=json.dumps({'provider':'s2','value':'test-fixture'}).encode()
        request=urllib.request.Request(self.base+'/api/configure',data=body,headers={
            'Content-Type':'application/json','Origin':'https://invalid.example','X-VR-Token':token})
        with patch.object(workspace_config.connections,'save') as save:
            with self.assertRaises(urllib.error.HTTPError) as rejected:
                urllib.request.urlopen(request)
        self.assertEqual(rejected.exception.code,403)
        save.assert_not_called()

    def test_explicit_connection_check_is_cached_outside_projects_and_requires_csrf(self):
        result={'checked_at':'now','providers':[{'provider':'arxiv','status':'passed','message':'test fixture'}]}
        body=json.dumps({'providers':['arxiv']}).encode()
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            urllib.request.urlopen(urllib.request.Request(self.base+'/api/preflight',data=body,headers={'Content-Type':'application/json'}))
        self.assertEqual(rejected.exception.code,403)
        with urllib.request.urlopen(self.base+'/api/session') as response:token=json.load(response)['token']
        request=urllib.request.Request(self.base+'/api/preflight',data=body,headers={'Content-Type':'application/json','Origin':self.base,'X-VR-Token':token})
        with patch.object(workspace_config.integrations,'preflight',return_value=result):
            with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response)['providers'][0]['status'],'passed')
        self.assertEqual(workspace_config.load(self.root)['arxiv']['status'],'passed')
        self.assertFalse((self.root/'.research').exists())

if __name__=='__main__':unittest.main()
