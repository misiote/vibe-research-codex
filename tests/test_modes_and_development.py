"""Cross-mode isolation, topic search and independent development observations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugins/vibe-research/runtime'))
from vr import modes,lightning,engineering,devtools,history,retrieval,experiments,brainstorm
from vr.store import Store,ResearchError

class Development(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=Store.init(self.root/'project','Question');self.addCleanup(self.store.db.close)
        self.repo=self.root/'repo';self.repo.mkdir()
        for args in [['init'],['-c','user.name=Test','-c','user.email=test@example.invalid','commit','--allow-empty','-m','fixture']]:
            subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)
    def apply(self,fn):
        with self.store.write('test',{}):return fn()
    def test_explicit_modes_are_conversation_scoped_and_do_not_register_projects(self):
        before=self.store.revision()
        a=modes.enter(self.root,'thread-a','lightning','Explore a topic')
        b=modes.enter(self.root,'thread-b','brainstorming','Prepare a proposal',topic='Cooperative agents')
        self.assertIn('draft',a);self.assertNotIn('draft',b);self.assertIn('board',b)
        self.assertEqual(modes.status(self.root,'thread-a')['mode'],'lightning')
        self.assertEqual(b['modules']['proposal']['skill'],'research-admin-expert')
        self.assertEqual(len(lightning.listing(self.root)['drafts']),1);self.assertEqual(len(brainstorm.listing(self.root)['spaces']),1)
        self.assertEqual(modes.enter(self.root,'thread-a','lightning')['draft'],a['draft'])
        modes.enter(self.root,'thread-a','engineering',project=self.store.root)
        self.assertEqual(modes.status(self.root,'thread-b')['mode'],'brainstorming')
        self.assertTrue((self.root/'projects.json').exists());self.assertEqual(before,self.store.revision())
        with self.assertRaises(ResearchError):modes.enter(self.root,'','lightning')
        with self.assertRaises(ResearchError):modes.enter(self.root,'x','brainstorming',project=self.store.root)
    def test_brainstorm_modules_are_optional_versioned_and_explicitly_linked(self):
        b=brainstorm.write(self.root,topic='Agent learning',context='Resource constraints')
        self.assertEqual(b['modules'],{})
        b=brainstorm.write(self.root,b['id'],module='proposal',content='Independent plan')
        self.assertFalse(b['modules']['proposal']['needs_review'])
        b=brainstorm.write(self.root,b['id'],module='history',content='Sourced history',sources=['https://example.org/paper'])
        self.assertFalse(b['modules']['proposal']['needs_review'])
        b=brainstorm.write(self.root,b['id'],module='directions',content='Candidate comparison',uses={'history':1})
        b=brainstorm.write(self.root,b['id'],module='history',content='Updated history')
        self.assertTrue(b['modules']['directions']['needs_review'])
        self.assertFalse(b['modules']['proposal']['needs_review'])
        with self.assertRaises(ResearchError):brainstorm.write(self.root,b['id'],module='history',content='Cycle',uses={'directions':1})
        with self.assertRaises(ResearchError):brainstorm.write(self.root,b['id'],module='directions',content='Old input',uses={'history':1})
        with self.assertRaises(ResearchError):brainstorm.write(self.root,b['id'],context='Overwrite',expected_updated_at='old')
        b=brainstorm.write(self.root,b['id'],context='Changed constraints')
        self.assertTrue(b['modules']['proposal']['needs_review'])
        self.assertEqual(brainstorm.packet(self.root,b['id'],'proposal')['skill'],'research-admin-expert')
        self.assertEqual(brainstorm.handoff(self.root,b['id'])['space'],b['id'])
        self.assertTrue((self.root/'projects.json').exists())
        with self.assertRaises(ResearchError):brainstorm.write(self.root,topic='')
        with self.assertRaises(ResearchError):brainstorm.show(self.root,'../escape')
    def test_topic_and_subtopic_do_not_depend_on_graph_neighborhood(self):
        with self.store.write('fixture',{}):
            p=self.store.add_node('P','Unrelated title',{'bibliography':{'year':2001}})
            h=self.store.add_node('H','A local hypothesis')
            history.record(self.store,{'title':'History','topic':'多智能体学习','coverage':'Fixture only','events':[
                {'id':'e1','date':'2001','kind':'method','title':'方法 A','description':'历史意义','topics':['credit assignment'],'sources':[p]},
                {'id':'e2','date':'2002','kind':'debate','title':'方法 B','description':'历史意义','topics':['communication'],'sources':[p],'local_nodes':[h]}]})
        a=history.snapshot(self.store,'local',topic='多智能体学习',subtopic='credit assignment')
        self.assertEqual([e['title'] for e in a['events']],['方法 A'])
        self.assertEqual(len(history.snapshot(self.store,topic='MARL',aliases='多智能体学习')['events']),2)
        self.assertTrue(history.snapshot(self.store)['needs_topic'])
        with self.assertRaises(ResearchError):history.snapshot(self.store,'local',h)
    def test_topic_queries_preserve_all_sources_and_do_not_import_candidates(self):
        before=self.store.revision()
        d=history.search(self.store,'reinforcement learning','local','offline RL','batch RL',since='2000',providers=['arxiv','crossref'])
        run=retrieval.snapshot(self.store.root,d['id'])['runs'][0]
        self.assertEqual({t['provider'] for t in run['tasks']},{'arxiv','crossref'})
        self.assertTrue(all('offline RL' in t['query'] for t in run['tasks']))
        self.assertEqual(before,self.store.revision());self.assertIsNone(d['worker'])
        with self.assertRaises(ResearchError):history.search_plan('topic','local')
    def make_link(self):
        return self.apply(lambda:engineering.link(self.store,{'repo':str(self.repo),'tools':{'github':'https://github.com/org/repo','wandb':'https://wandb.ai/team/project','mlflow':'http://127.0.0.1:5000'},'ssh':{'host':'gpu-box','repo':'/home/user/research'},'mlflow_experiments':['0'],'metric_keys':['loss']}))
    def test_independent_adapters_keep_success_when_another_fails(self):
        link=self.make_link();commit=link['commit']
        with patch.dict(devtools.ADAPTERS,{'github':lambda _: {'commits':[{'commit':commit}]},'wandb':lambda _: (_ for _ in ()).throw(RuntimeError('secret-token')),'mlflow':lambda _:{'runs':[{'id':'run-1','commit':commit,'state':'RUNNING'}]},'ssh':lambda _:{'commit':commit}}):
            d=self.apply(lambda:engineering.sync(self.store,link['id'],True))
        self.assertEqual(d['observations']['wandb']['status'],'unavailable')
        self.assertEqual(d['observations']['mlflow']['status'],'observed')
        self.assertNotIn('secret-token',json.dumps(d));self.assertGreater(len(d['commit_groups'][0]['sources']),2)
        with patch.dict(devtools.ADAPTERS,{'github':lambda _:self.fail('Network access without opt-in')}):
            d=self.apply(lambda:engineering.sync(self.store,link['id'],False))
        self.assertEqual(d['observations']['github']['status'],'not_checked')
    def test_remote_only_link_and_ssh_arguments_are_literal(self):
        result=self.apply(lambda:engineering.link(self.store,{'ssh':{'host':'gpu-box','repo':"/home/user/a; echo nope"}}))
        self.assertIsNone(result['repo']);self.assertEqual(result['ssh']['host'],'gpu-box')
        with patch.object(devtools,'command',return_value='a'*40+'\n M file.py\n') as call:
            out=devtools.ssh(result)
        args=call.call_args[0][0];self.assertIn('BatchMode=yes',args);self.assertIn('StrictHostKeyChecking=yes',args)
        self.assertIn("'/home/user/a; echo nope'",args[-1]);self.assertEqual(out['changed_files'],1)
    def test_link_rejects_credentials_bad_hosts_and_ssh_options(self):
        for spec in [{'repo':str(self.repo),'tools':{'wandb':'https://evil.example/team/project'}},{'ssh':{'host':'-oProxyCommand=bad','repo':'/tmp/x'}},{'repo':str(self.repo),'tools':{'mlflow':'https://user:secret@example.org'}},{'repo':str(self.repo),'api_key':'secret'}]:
            before=self.store.revision()
            with self.assertRaises(ResearchError):self.apply(lambda:engineering.link(self.store,spec))
            self.assertEqual(before,self.store.revision())
    def test_work_package_completion_needs_traceable_acceptance_and_never_changes_hypothesis(self):
        link=self.make_link()
        t=self.apply(lambda:engineering.task(self.store,{'title':'Implement baseline','question':'Does it work?','acceptance':'Matches expected output','protocol':'Held out test','stop_rule':'Stop if invalid','refs':[link['id']]}))
        with self.assertRaises(ResearchError):self.apply(lambda:engineering.task(self.store,{'id':t['id'],'state':'completed','note':'Done'}))
        self.apply(lambda:engineering.task(self.store,{'id':t['id'],'state':'working','note':'Implementing'}))
        self.apply(lambda:engineering.task(self.store,{'id':t['id'],'state':'completed','note':'Reviewed output','evidence':[link['id']]}))
        self.assertEqual(self.store.get(t['id'])['data']['execution_status'],'completed')
    def test_mlflow_and_wandb_read_contracts_and_metric_allowlist(self):
        link=self.make_link()
        with patch.dict(os.environ,{'WANDB_API_KEY':'test-key'}),patch.object(devtools,'request',return_value={'data':{'project':{'runs':{'edges':[{'node':{'name':'r','displayName':'run','state':'running','commit':'a'*40,'summaryMetrics':'{"loss":0.2,"secret":"nope","accuracy":1}'}}]}}}}) as req:
            d=devtools.wandb(link)
        self.assertEqual(d['runs'][0]['metrics'],{'loss':0.2});self.assertNotIn('test-key',json.dumps(d))
        with patch.object(devtools,'request',return_value={'runs':[{'info':{'run_id':'r','status':'RUNNING'},'data':{'tags':[{'key':'mlflow.source.git.commit','value':'a'*40}],'metrics':[{'key':'loss','value':0.1}]}}]}) as req:
            d=devtools.mlflow(link)
        self.assertEqual(req.call_args[0][1]['experiment_ids'],['0']);self.assertEqual(d['runs'][0]['commit'],'a'*40)
    def test_generic_experiments_do_not_require_marl_fields(self):
        spec={k:'Specified' for k in ('command','repo','config','baselines','compute_budget','data_split','success_threshold','stop_rule')}
        spec.update(profile='generic',seeds=[1,2],metrics=['accuracy'])
        self.assertEqual(experiments.validate(spec),[])
        spec.pop('data_split');self.assertTrue(experiments.validate(spec))

if __name__=='__main__':unittest.main()
