import json,sys,tempfile,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'plugins/vibe-research/runtime'))
from vr import workflow,giver,brainstorm
from vr.store import ResearchError

class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.initial=giver.init(self.root,'Workflow fixture',branch='ideas/main')
        self.board=giver.row(self.root,self.initial['project'])['board']
        self.context={'branch':'ideas/main','session':'chat-a','event':'milestone','intent':'implement','goal':'Prototype baseline','reason':'已选择方案并准备本地实现','milestone':'proposal-v1'}
    def write(self,**spec):return brainstorm.write(self.root,self.board,**spec)
    def assess(self,**changes):return workflow.assess(self.root,{**self.context,**changes})
    def record(self,decision,context=None,proposal=None,**extra):
        context=context or self.context;proposal=proposal or workflow.evaluate(self.root,context)['id']
        return workflow.record(self.root,{'context':context,'proposal':proposal,'decision':decision,**extra})
    def ready(self):self.write(module='directions',content='可复现基线方案')
    def test_read_only_and_no_keyword_classifier(self):
        before=list(self.root.rglob('*'));self.assess();self.assertEqual(before,list(self.root.rglob('*')))
        self.ready();r=self.assess(intent='continue',reason='正文中出现 implement、engineering、汇报')
        self.assertEqual(r['action'],'checkpoint');self.assertEqual(r['delivery'],'automatic')
        self.assertEqual(self.assess(event='resume')['delivery'],'none')
        self.assertEqual(self.assess(event='blocked')['delivery'],'none')
    def test_readiness_and_stale_materials(self):
        self.assertEqual(self.assess()['action'],'continue')
        self.ready();self.assertEqual(self.assess()['target'],'engineering')
        self.write(module='history',content='v1');self.write(module='directions',content='derived',uses={'history':1});self.write(module='history',content='v2')
        self.assertEqual(self.assess()['action'],'review_inputs')
    def test_user_choices_deduplicate_across_chats_and_minor_updates(self):
        self.ready();self.record('presented');self.assertTrue(self.assess(session='chat-b')['suppressed'])
        self.record('defer');self.ready();self.assertTrue(self.assess()['suppressed'])
        self.assertEqual(self.assess(milestone='proposal-v2')['delivery'],'ask')
        self.record('decline');self.assertTrue(self.assess(milestone='proposal-v3')['suppressed'])
        self.assertEqual(self.assess(explicit=True,event='user_request')['delivery'],'execute')
    def test_accept_needs_user_choice_and_source_version(self):
        self.ready();old=self.assess()
        with self.assertRaises(ResearchError):self.record('accept')
        self.record('presented');self.write(module='directions',content='Changed plan')
        with self.assertRaises(ResearchError):self.record('accept',proposal=old['id'])
        self.record('presented');self.record('accept');self.assertTrue(self.assess()['suppressed'])
    def test_completed_conversion_uses_verified_receipt_and_does_not_repeat(self):
        self.ready();r=self.assess();self.record('presented');self.record('accept')
        with self.assertRaises(ResearchError):self.record('applied',proposal=r['id'],receipt={'branch':'made-up','project':'fake'})
        dest=giver.fork(self.root,'ideas/main','engineering/v1','engineering')
        self.record('applied',proposal=r['id'],receipt=dest)
        self.write(module='directions',content='Source evolves independently')
        self.assertTrue(self.assess()['suppressed'])
    def test_report_is_not_always_a_new_project(self):
        giver.fork(self.root,'ideas/main','engineering/v1','engineering')
        self.assertEqual(self.assess(branch='engineering/v1',intent='report')['action'],'continue')
        self.assertEqual(self.assess(branch='engineering/v1',intent='report',persistent=True)['target'],'brainstorming')
    def test_explicit_commands_skip_question_and_switch_checks_session(self):
        self.ready();self.assertEqual(self.assess(explicit=True,event='user_request')['delivery'],'execute')
        giver.fork(self.root,'ideas/main','ideas/other')
        r=self.assess(target='ideas/other',intent='continue');self.assertEqual(r['action'],'switch')
        with self.assertRaises(ResearchError):self.assess(target='ideas/other',session='')
        giver.switch(self.root,'ideas/other','chat-a')
        self.assertEqual(giver.status(self.root,session='chat-a')['active'],'ideas/other')
    def test_checkpoint_completion_survives_head_change(self):
        self.ready();context={**self.context,'intent':'continue'};r=workflow.assess(self.root,context)
        self.record('accept',context=context)
        with self.assertRaises(ResearchError):self.record('applied',context=context,proposal=r['id'],receipt={'commit':r['head']})
        receipt=giver.commit(self.root,'ideas/main','Milestone saved')
        self.record('applied',context=context,proposal=r['id'],receipt=receipt)
        self.record('applied',context=context,proposal=r['id'],receipt=receipt)
        self.assertEqual(workflow.assess(self.root,context)['action'],'continue')
    def test_archived_or_unknown_context_never_auto_selects(self):
        from vr import hub
        self.assertEqual(workflow.assess(self.root,{'event':'resume','goal':'Resume'})['delivery'],'none')
        hub.lifecycle(self.root/'projects.json',self.initial['project'],'archive','Fixture')
        self.assertEqual(self.assess()['delivery'],'none')
    def test_management_does_not_switch_or_fork_by_itself(self):
        self.ready();self.record('presented');self.record('defer')
        self.assertEqual(len(giver.load(self.root)['branches']),1);self.assertEqual(giver.load(self.root)['sessions'],{})
    def test_one_pending_question_per_project_goal(self):
        self.ready();self.record('presented')
        self.assertEqual(self.assess(intent='alternative')['previous_decision'],'another_pending')
        self.assertEqual(self.assess(intent='alternative',goal='Different task')['delivery'],'ask')

if __name__=='__main__':unittest.main()
