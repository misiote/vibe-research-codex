"""Mode conversion always creates an independently owned research branch."""
import json,sys,tempfile,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'plugins/vibe-research/runtime'))
from vr import brainstorm,bridge,giver,hub
from vr.store import Store,ResearchError

class Transfers(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.board=brainstorm.write(self.root,topic='Independent research',context='Question')
        self.board=brainstorm.write(self.root,self.board['id'],module='directions',content='A falsifiable idea',sources=['https://example.org/paper'])
    def spec(self,direction,**spec):return {'direction':direction,'request_id':str(uuid.uuid4()),**spec}
    def test_conversion_retains_full_material_and_only_plans_implementation(self):
        before=brainstorm.show(self.root,self.board['id']);result=bridge.transfer(self.root,self.spec('promote',board=self.board['id']))
        self.assertEqual(brainstorm.show(self.root,self.board['id']),before)
        dest=giver.row(self.root,result['project']);store=Store(dest['root'])
        try:
            tasks=[n for n in store.rows('nodes') if n['data'].get('source_type')=='engineering_task']
            self.assertEqual(len(tasks),1);self.assertEqual(tasks[0]['data']['execution_status'],'planned')
            self.assertFalse(any(n['kind']=='H' for n in store.rows('nodes')))
            material=json.loads((Path(dest['root'])/'.research/giver-modules.json').read_text());self.assertEqual(material['modules'],before['modules'])
        finally:store.db.close()
    def test_each_direction_creates_new_identity_and_retry_is_idempotent(self):
        spec=self.spec('promote',board=self.board['id']);first=bridge.transfer(self.root,spec);self.assertEqual(bridge.transfer(self.root,spec),first)
        reverse=bridge.transfer(self.root,self.spec('abstract',project=first['project']))
        self.assertEqual(len(hub.entries(self.root/'projects.json')),3)
        self.assertNotEqual(reverse['board'],self.board['id']);self.assertNotEqual(reverse['project'],first['project'])
        board=brainstorm.show(self.root,reverse['board']);self.assertIn('progress',board['modules']);self.assertEqual(board['modules']['directions']['content'],'A falsifiable idea')
    def test_stale_sources_and_changed_request_rejected(self):
        bad=self.spec('promote',board=self.board['id'],expected_updated_at='stale')
        with self.assertRaises(ResearchError):bridge.transfer(self.root,bad)
        bad.pop('expected_updated_at');bridge.transfer(self.root,bad);bad['idea']='Changed request'
        with self.assertRaises(ResearchError):bridge.transfer(self.root,bad)
    def test_target_reuse_is_rejected_without_registering_project(self):
        before=len(hub.entries(self.root/'projects.json'))
        with self.assertRaises(ResearchError):bridge.transfer(self.root,self.spec('promote',board=self.board['id'],target=self.board['project']))
        self.assertEqual(len(hub.entries(self.root/'projects.json')),before)
    def test_empty_idea_and_invalid_environment_do_not_create_project(self):
        empty=brainstorm.write(self.root,topic='Empty');before=len(hub.entries(self.root/'projects.json'))
        with self.assertRaises(ResearchError):bridge.transfer(self.root,self.spec('promote',board=empty['id']))
        with self.assertRaises(ResearchError):bridge.transfer(self.root,self.spec('promote',board=self.board['id'],environment={'tools':{'unknown':'https://example.org'}}))
        self.assertEqual(len(hub.entries(self.root/'projects.json')),before)

if __name__=='__main__':unittest.main()
