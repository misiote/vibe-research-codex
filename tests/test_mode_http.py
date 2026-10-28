import json
import uuid
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'plugins/vibe-research/runtime'))
from vr import watch,hub,activity,retrieval
from vr.store import Store

class ModeHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        s=Store.init(self.root/'project','Topic');s.db.close();self.registry=self.root/'projects.json'
        self.project=hub.register(self.registry,self.root/'project','Fixture')
        self.server=watch.server(self.root,0,self.registry);threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.op=urllib.request.build_opener(urllib.request.ProxyHandler({}));self.token=self.get('/api/session')['token']
    def get(self,path):
        with self.op.open(self.base+path) as r:return json.load(r)
    def post(self,path,data):
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':self.base,'X-VR-Token':self.token})
        with self.op.open(req) as r:return json.load(r)
    def test_workspace_and_project_help_routes(self):
        for prefix in ('','/p/'+self.project['id']):
            for path,expected in [('/settings/skills/giver','GIt VibE Research'),('/settings/skills/vrpet','companion.py'),('/settings/connections/scopus','Scopus')]:
                with self.subTest(path=prefix+path),self.op.open(self.base+prefix+path) as response:
                    self.assertEqual(response.status,200)
                    self.assertIn(expected,response.read().decode())
    def test_project_navigation_resources_and_both_mode_data_scopes(self):
        initial=self.post('/api/giver',{'action':'init','spec':{'title':'Brainstorm navigation fixture','mode':'brainstorming','branch':'ideas/navigation'}})
        for project,title in [(initial['project'],'Brainstorm navigation fixture'),(self.project['id'],'Topic')]:
            prefix='/p/'+project
            self.assertEqual(self.get(prefix+'/api/state')['question'],title)
            for page in [prefix+'/',prefix+'/explore',prefix+'/graph']:
                with self.subTest(page=page),self.op.open(self.base+page) as response:self.assertEqual(response.status,200)
        for page in ['/brainstorming','/p/'+self.project['id']+'/engineering','/p/'+initial['project']+'/', '/p/'+initial['project']+'/explore']:
            with self.subTest(page=page),self.op.open(self.base+page) as response:
                body=response.read().decode();self.assertIn('/static/project_nav.js',body);self.assertIn('id="project-navigation"',body)
        with self.op.open(self.base+'/static/project_nav.js') as response:self.assertEqual(response.status,200)
    def test_brainstorm_http_modules_are_separate_from_lightning_and_project(self):
        before=(self.registry.read_bytes(),(self.root/'project/.research/nodes.json').read_bytes())
        b=self.post('/api/brainstorm',{'action':'start','spec':{'topic':'Research topic'}})
        b=self.post('/api/brainstorm',{'action':'update','id':b['id'],'spec':{'module':'proposal','content':'Planned work','expected_updated_at':b['updated_at']}})
        self.assertEqual(b['modules']['proposal']['revision'],1)
        p=self.post('/api/brainstorm',{'action':'packet','id':b['id'],'module':'proposal'})
        self.assertEqual(p['skill'],'research-admin-expert')
        self.assertEqual(self.get('/api/lightning')['drafts'],[])
        self.assertEqual(before[1],(self.root/'project/.research/nodes.json').read_bytes());self.assertTrue(any(p['mode']=='brainstorming' for p in self.get('/api/projects')['projects']))
        with self.op.open(self.base+'/brainstorming') as r:body=r.read().decode()
        self.assertNotIn('草稿箱',body);self.assertIn('Research modes',body)
    def test_engineering_routes_and_topic_landing(self):
        prefix='/p/'+self.project['id']
        self.assertEqual(self.get(prefix+'/api/research/engineering')['links'],[])
        self.assertTrue(self.get(prefix+'/api/research/history')['needs_topic'])
        self.assertTrue(all('kind' in n for n in self.get(prefix+'/api/state')['nodes'].values()))
        for page in ['/lightning','/engineering',prefix+'/engineering','/static/modes.css']:
            with self.op.open(self.base+page) as r:self.assertEqual(r.status,200)
        plan=self.post(prefix+'/api/research',{'action':'engineering_task','spec':{'title':'Task','question':'Q','acceptance':'A','protocol':'P','stop_rule':'S','refs':['RQ0001']}})
        self.assertEqual(plan['status'],'planned')

    def test_bidirectional_bridge_http_roundtrip(self):
        b=self.post('/api/brainstorm',{'action':'start','spec':{'topic':'HTTP roundtrip'}})
        b=self.post('/api/brainstorm',{'action':'update','id':b['id'],'spec':{'module':'directions','content':'Testable idea'}})
        spec={'direction':'promote','request_id':str(uuid.uuid4()),'board':b['id'],'expected_updated_at':b['updated_at']}
        preview=self.post('/api/bridge',{'action':'preview','spec':spec});self.assertEqual(preview['topic'],'HTTP roundtrip')
        result=self.post('/api/bridge',{'action':'transfer','spec':spec});self.assertNotEqual(result['project'],self.project['id'])
        self.assertEqual(self.post('/api/bridge',{'action':'transfer','spec':spec}),result)
        reverse={'direction':'abstract','request_id':str(uuid.uuid4()),'project':result['project']}
        report=self.post('/api/bridge',{'action':'preview','spec':reverse});reverse['source_revision']=report['packet']['revision']
        returned=self.post('/api/bridge',{'action':'transfer','spec':reverse})
        self.assertNotEqual(returned['board'],b['id'])
        updated=self.get('/api/brainstorm?id='+returned['board']);self.assertEqual(updated['modules']['directions']['content'],'Testable idea');self.assertIn('progress',updated['modules'])

    def test_management_and_discard_preserve_research_files(self):
        original=(self.root/'project/.research/nodes.json').read_bytes()
        for action,expected in [('archive','archived'),('restore','active'),('remove','removed'),('restore','active')]:
            self.post('/api/manage',{'action':action,'id':self.project['id'],'reason':'Independent UI regression'})
            row=next(r for r in self.get('/api/projects')['projects'] if r['id']==self.project['id'])
            self.assertEqual(row['lifecycle'],expected)
            self.assertEqual((self.root/'project/.research/nodes.json').read_bytes(),original)
        draft=self.post('/api/lightning',{'action':'start','draft':{'title':'Disposable fixture','body':'UI test','mode':'lightning'}})
        result=self.post('/api/lightning',{'action':'discard','id':draft['id']})
        self.assertTrue(result['discarded'])
        self.assertNotIn(draft['id'],[r['id'] for r in self.get('/api/lightning')['drafts']])
        with self.op.open(self.base+'/static/actions.js') as response:
            self.assertEqual(response.status,200)
            self.assertIn('javascript',response.headers['Content-Type'])

    def test_archive_and_remove_do_not_require_pausing_work_or_retrieval(self):
        store=Store(self.root/'project')
        try:
            original_revision=store.revision()
            run=activity.write(store,'start',title='Still running',why='Test active project visibility',next_step='Continue independently')
            retrieval.start(store.root,'Pending search',['fixture'],['arxiv'],'Synthetic verification')
            for state in ['working','waiting','blocked']:
                activity.write(store,'update',ident=run['id'],state=state,message='Keep existing work state',next_step='Continue independently')
                before=activity.snapshot(store.root,set())['current']
                queue_before=retrieval.snapshot(store.root)
                for action in ['archive','restore','remove','restore']:
                    self.post('/api/manage',{'action':action,'id':self.project['id'],'reason':'User checked running tasks and confirmed'})
                    self.assertEqual(activity.snapshot(store.root,set())['current'],before)
                    self.assertEqual(retrieval.snapshot(store.root)['runs'],queue_before['runs'])
                self.assertEqual(store.revision(),original_revision)
        finally:store.db.close()

    def test_independent_project_visibility_and_giver_http(self):
        initial=self.post('/api/giver',{'action':'init','spec':{'title':'Typed idea','mode':'brainstorming','branch':'ideas/main'}})
        state=self.get('/api/giver');self.assertEqual(len(state['branches']),2)
        owner=initial['project'];board=next(b for b in self.get('/api/brainstorm')['spaces'] if b['project']==owner)
        child=self.post('/api/giver',{'action':'branch','spec':{'source':'ideas/main','branch':'engineering/prototype','mode':'engineering','request_id':str(uuid.uuid4())}})
        self.assertNotEqual(owner,child['project'])
        self.post('/api/manage',{'action':'remove','id':child['project'],'reason':'Independent child visibility'})
        self.assertIn(board['id'],[b['id'] for b in self.get('/api/brainstorm')['spaces']])
        for action,visible in [('archive',False),('restore',True),('remove',False),('restore',True)]:
            self.post('/api/manage',{'action':action,'id':owner,'reason':'Project visibility fixture'})
            self.assertEqual(board['id'] in [b['id'] for b in self.get('/api/brainstorm')['spaces']],visible)
            self.assertIn(board['id'],[b['id'] for b in self.get('/api/brainstorm?include_hidden=1')['spaces']])
        with self.op.open(self.base+'/giver') as response:self.assertEqual(response.status,200)
        with self.op.open(self.base+'/static/giver.js') as response:self.assertEqual(response.status,200)
        comparison=self.post('/api/giver',{'action':'diff','spec':{'left':'ideas/main','right':'engineering/prototype'}})
        self.assertIn('changes',comparison)

if __name__=='__main__':unittest.main()
