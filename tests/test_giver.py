import json,sys,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'plugins/vibe-research/runtime'))
from vr import giver,brainstorm,hub,bridge,maintenance
from vr.store import Store,ResearchError

class Giver(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.initial=giver.init(self.root,'Research fixture',branch='ideas/main')
        self.project=giver.row(self.root,self.initial['project']);self.board=self.project['board']
    def write(self,board,content):return brainstorm.write(self.root,board,module='directions',content=content)
    def test_projects_and_forks_are_independent_and_typed(self):
        self.write(self.board,'Original idea');before=brainstorm.show(self.root,self.board)
        child=giver.fork(self.root,'ideas/main','implementation/v1',mode='engineering')
        grand=giver.fork(self.root,'implementation/v1','report/v1',mode='brainstorming')
        self.assertEqual(len(hub.entries(self.root/'projects.json')),3)
        self.assertNotEqual(child['project'],self.initial['project']);self.assertNotEqual(grand['board'],self.board)
        self.assertEqual(brainstorm.show(self.root,grand['board'])['modules']['directions']['content'],'Original idea')
        self.write(grand['board'],'Independent report');self.assertEqual(brainstorm.show(self.root,self.board),before)
        state=giver.status(self.root);self.assertEqual(len(state['branches']),3)
        self.assertEqual(giver.row(self.root,child['project'])['mode'],'engineering')
        hub.lifecycle(self.root/'projects.json',self.initial['project'],'remove','Independent visibility')
        self.assertIn(grand['board'],[b['id'] for b in brainstorm.listing(self.root)['spaces']])
    def test_snapshots_diff_tags_restore_and_historical_fork(self):
        self.write(self.board,'Version one');first=giver.commit(self.root,'ideas/main','v1')['commit'];self.write(self.board,'Version two')
        self.assertIn('modules/directions',[d['path'] for d in giver.diff(self.root,'ideas/main')['changes']])
        second=giver.commit(self.root,'ideas/main','v2')['commit'];giver.tag(self.root,'proposal-v1',first)
        self.assertEqual(giver.object_data(self.root,giver.load(self.root),'proposal-v1')['modules/directions']['content'],'Version one')
        old=giver.fork(self.root,first,'ideas/historical');self.assertEqual(brainstorm.show(self.root,old['board'])['modules']['directions']['content'],'Version one')
        giver.restore(self.root,'ideas/main',first,['modules/directions']);self.assertEqual(brainstorm.show(self.root,self.board)['modules']['directions']['content'],'Version one')
        self.assertIn(second,giver.load(self.root)['commits'])
    def test_merge_commands_are_not_part_of_the_research_model(self):
        with self.assertRaises(ResearchError):giver.execute(self.root,'merge',{'source':'ideas/main','target':'ideas/other'})
        with self.assertRaises(ResearchError):giver.execute(self.root,'cherry-pick',{'source':'unknown'})

    def test_retry_reuses_project_and_branch_and_sessions_are_independent(self):
        ident=str(uuid.uuid4());first=giver.fork(self.root,'ideas/main','ideas/retry',request_id=ident)
        self.write(self.board,'Later source changes');self.assertEqual(giver.fork(self.root,'ideas/main','ideas/retry',request_id=ident),first)
        self.assertEqual(len(hub.entries(self.root/'projects.json')),2)
        giver.switch(self.root,'ideas/main','chat-a');giver.switch(self.root,'ideas/retry','chat-b')
        self.assertEqual(giver.status(self.root,session='chat-a')['active'],'ideas/main')
        self.assertEqual(giver.status(self.root,session='chat-b')['active'],'ideas/retry')
    def test_bridge_always_creates_new_project_and_rejects_reused_target(self):
        self.write(self.board,'Testable idea');spec={'direction':'promote','board':self.board,'request_id':str(uuid.uuid4())}
        before=brainstorm.show(self.root,self.board);result=bridge.transfer(self.root,spec)
        self.assertNotEqual(result['project'],self.project['id']);self.assertEqual(brainstorm.show(self.root,self.board),before)
        self.assertEqual(bridge.transfer(self.root,spec),result)
        with self.assertRaises(ResearchError):bridge.transfer(self.root,{**spec,'target':self.project['id']})
        reverse=bridge.transfer(self.root,{'direction':'abstract','project':result['project'],'request_id':str(uuid.uuid4())})
        self.assertNotEqual(reverse['project'],self.project['id']);self.assertNotEqual(reverse['board'],self.board)
    def test_failed_fork_recovery_keeps_prepared_base(self):
        ident=str(uuid.uuid4())
        with patch('vr.giver.hub.register',side_effect=ResearchError('Interrupted after clone')):
            with self.assertRaises(ResearchError):giver.fork(self.root,'ideas/main','ideas/recover',request_id=ident)
        prepared=json.loads((giver.home(self.root)/'requests'/(ident+'.json')).read_text());self.write(self.board,'New live source');new_head=giver.commit(self.root,'ideas/main','Independent new commit')['commit']
        result=giver.fork(self.root,'ideas/main','ideas/recover',request_id=ident)
        self.assertEqual(giver.load(self.root)['branches']['ideas/main']['head'],new_head);self.assertEqual(result['base'],prepared['base']);self.assertNotIn('directions',brainstorm.show(self.root,result['board'])['modules'])
    def test_attachments_are_copied_into_an_independent_project(self):
        source=self.root/'paper.txt';source.write_text('Synthetic attachment')
        store=Store(self.project['root'])
        try:
            with store.write('fixture.attachment',{}):store.add_node('A','Synthetic attachment',{'artifacts':[store.artifact(source)]})
        finally:store.db.close()
        child=giver.fork(self.root,'ideas/main','engineering/with-material','engineering')
        left=Path(self.project['root'])/'.research/artifacts';right=Path(giver.row(self.root,child['project'])['root'])/'.research/artifacts'
        self.assertNotEqual(left,right);self.assertEqual({p.name:p.read_bytes() for p in left.iterdir()},{p.name:p.read_bytes() for p in right.iterdir()})
    def test_modified_snapshot_is_detected(self):
        state=giver.load(self.root);ident=self.initial['commit'];path=giver.home(self.root)/'objects'/ident/'snapshot.json'
        path.write_text('{}')
        with self.assertRaises(ResearchError):giver.object_data(self.root,state,ident)

    def test_reset_backups_are_verified_and_leave_configuration(self):
        (self.root/'configuration.json').write_text('keep');(self.root/'.vibe-research/companion').mkdir();(self.root/'.vibe-research/companion/state').write_text('keep')
        with self.assertRaises(ResearchError):maintenance.reset(self.root)
        result=maintenance.reset(self.root,True);backup=Path(result['backup'])
        self.assertTrue((backup/'originals/projects.json').exists());self.assertEqual(hub.entries(self.root/'projects.json'),[])
        self.assertEqual((self.root/'configuration.json').read_text(),'keep');self.assertTrue((self.root/'.vibe-research/companion/state').exists())
        self.assertEqual(brainstorm.listing(self.root)['spaces'],[])

if __name__=='__main__':unittest.main()
