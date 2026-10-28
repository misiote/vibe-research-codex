"""Behavioral invariants for depth, draft isolation, history and decision support."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

PLUGIN = Path(__file__).resolve().parents[1] / 'plugins/vibe-research'
sys.path.insert(0, str(PLUGIN / 'runtime'))
from vr import reading, lightning, history, directions, watch, hub, resources
from vr.store import Store, ResearchError


class Modes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='vr-modes-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store.init(self.root / 'project', 'Question')
        self.addCleanup(self.store.db.close)
        with self.store.write('fixture', {}):
            self.paper = self.store.add_node('P', 'First method', {'bibliography': {'year': 2019, 'abstract': 'A method reports an improvement.'}})
            self.other = self.store.add_node('P', 'Independent route', {'bibliography': {'year': 2021}})
            self.hypothesis = self.store.add_node('H', 'Better performance')
            self.store.add_edge(self.hypothesis, 'derived_from', self.paper)

    def apply(self, fn):
        with self.store.write('test', {}): return fn()

    def note(self, depth='summary', basis='title_abstract'):
        return {'depth': depth, 'basis': basis, **{k: 'Explicit finding / unknown' for k in ('problem', 'method', 'results', 'limitations', 'relevance', 'unknowns')}}

    def attach(self, text='Method page one\fResults page two'):
        source = self.root / 'paper.txt'; source.write_text(text)
        return self.apply(lambda: reading.attach(self.store, self.paper, source))

    def test_task_defaults_and_user_override(self):
        self.assertEqual(reading.plan('slides')['depth'], 'summary')
        self.assertEqual(reading.plan('history')['depth'], 'skim')
        self.assertEqual(reading.plan('reproduce')['depth'], 'deep')
        self.assertEqual(reading.plan('reproduce', 'summary')['depth'], 'summary')

    def test_summary_needs_no_fulltext_and_creates_no_evidence(self):
        self.apply(lambda: reading.triage(self.store, self.paper, 'valuable', 'Relevant', depth='summary'))
        self.assertEqual(reading.queue(self.store)[0]['action'], 'summary')
        packet = reading.packet(self.store, self.paper)
        self.assertEqual(packet['basis'], 'title_abstract')
        result = self.apply(lambda: reading.save_note(self.store, self.paper, self.note()))
        self.assertFalse(result['evidence_verified'])
        self.assertFalse(reading.queue(self.store))
        self.assertFalse([n for n in self.store.rows('nodes') if n['kind'] == 'V'])
        self.assertIn('Explicit finding', resources.reading_page(self.store, self.paper))
        self.assertNotEqual(self.store.get(self.paper)['data'].get('reading_status'), 'complete')

    def test_skim_rejects_abstract_and_requires_fulltext(self):
        with self.assertRaises(ResearchError): self.apply(lambda: reading.save_note(self.store, self.paper, self.note('skim')))
        self.apply(lambda: reading.triage(self.store, self.paper, 'valuable', 'Relevant', depth='skim'))
        self.assertEqual(reading.queue(self.store)[0]['action'], 'acquire_fulltext')
        self.attach()
        self.assertEqual(reading.queue(self.store)[0]['action'], 'skim')
        self.apply(lambda: reading.save_note(self.store, self.paper, self.note('skim', 'fulltext')))
        self.assertFalse(reading.queue(self.store))
        self.attach('Updated paper version')
        self.assertEqual(reading.queue(self.store)[0]['action'], 'skim')

    def test_title_only_cannot_masquerade_as_summary(self):
        with self.assertRaises(ResearchError): self.apply(lambda: reading.save_note(self.store, self.other, self.note()))

    def test_legacy_deep_queue_remains_compatible(self):
        self.apply(lambda: reading.triage(self.store, self.paper, 'valuable', 'Relevant'))
        self.assertEqual(reading.queue(self.store)[0]['action'], 'acquire_fulltext')
        self.attach()
        self.assertEqual(reading.queue(self.store)[0]['action'], 'systematic_reading')
        self.assertEqual(len(reading.packet(self.store, self.paper)['required_sections']), 9)

    def test_lightning_cli_never_touches_active_project_or_registry(self):
        revision = self.store.revision()
        workspace = self.root / 'workspace'
        command = [sys.executable, str(PLUGIN / 'runtime/bin/vr'), '--project', str(self.store.root), 'lightning']
        result = json.loads(subprocess.check_output(command + ['start', '--workspace', str(workspace)]))
        self.assertFalse((workspace / 'projects.json').exists())
        self.assertFalse((workspace / 'projects').exists())
        self.assertFalse((workspace / '.research').exists())
        self.assertFalse((self.store.home / 'activity.db').exists())
        lightning.write(workspace, result['id'], title='Draft', task='slides', output='Real text')
        self.assertEqual(lightning.packet(workspace, result['id'])['reading_plan']['depth'], 'summary')
        lightning.discard(workspace, result['id'])
        self.assertEqual(lightning.listing(workspace)['drafts'], [])
        self.assertEqual(self.store.revision(), revision)

    def test_lightning_blocks_traversal_and_invalid_payload(self):
        for ident in ('../projects', '/tmp/x', 'Lnothex'):
            with self.assertRaises(ResearchError): lightning.show(self.root, ident)
        with self.assertRaises(ResearchError): lightning.write(self.root, task='shell')
        with self.assertRaises(ResearchError): lightning.write(self.root, title={})

    def timeline_spec(self):
        return {'title': 'Direction history', 'topic': 'Methods', 'coverage': 'Two seed papers; not complete', 'events': [
            {'id': 'origin', 'date': '2019', 'kind': 'method', 'title': 'Origin', 'description': 'Source-bounded explanation', 'sources': [self.paper], 'topics':['representation'], 'local_nodes': [self.hypothesis]},
            {'id': 'follow', 'date': '2021-02', 'kind': 'debate', 'title': 'Challenge', 'description': 'Independent route', 'sources': [self.other]}],
                'relations': [{'source': 'origin', 'target': 'follow', 'reason': 'Shared assumption, explicitly challenged'}]}

    def test_history_global_local_dates_and_relation_filtering(self):
        self.apply(lambda: history.record(self.store, self.timeline_spec()))
        global_ = history.snapshot(self.store,topic="Methods")
        self.assertEqual([e['date'] for e in global_['events']], ['2019', '2021-02'])
        self.assertEqual(len(global_['relations']), 1)
        local = history.snapshot(self.store,'local',topic='Methods',subtopic='representation')
        self.assertEqual([e['title'] for e in local['events']], ['Origin'])
        self.assertFalse(local['relations'])
        self.assertEqual(len(history.snapshot(self.store, topic='Methods', since='2021', until='2021')['events']), 1)
        with self.assertRaises(ResearchError): history.snapshot(self.store, 'local')

    def test_history_refuses_unsourced_or_invalid_date_and_rolls_back(self):
        before = self.store.revision()
        for field, value in [('sources', []), ('date', '2021-02-30')]:
            spec = self.timeline_spec(); spec['events'][0][field] = value
            with self.assertRaises(ResearchError): self.apply(lambda: history.record(self.store, spec))
        self.assertEqual(self.store.revision(), before)
        self.assertEqual([e['date'] for e in history.snapshot(self.store,topic='method,route')['events']], ['2019', '2021'])

    def comparison(self, evidence=None):
        candidate = {'id': 'a', 'title': 'Route A', 'hypothesis': 'Falsifiable', 'contribution': 'Increment', 'risks': 'Confound', 'minimum_test': 'Controlled comparison', 'success_threshold': 'Predefined delta', 'stop_rule': 'No useful gain', 'revival_condition': 'New data', 'hard_constraints': [{'name': 'Data', 'status': 'pass', 'reason': 'Available'}], 'nearest_work': [self.paper], 'counterevidence': [], 'criteria': {k: {'range': [3, 4], 'reason': 'Explicit rationale', 'evidence': evidence or []} for k in directions.CRITERIA}}
        other = copy.deepcopy(candidate);other.update(id='b',title='Route B')
        for a in other['criteria'].values(): a['range'] = [1, 2]
        return {'question': 'Choose route', 'constraints': 'One week', 'coverage': 'Two known papers only', 'candidates': [candidate, other]}

    def test_direction_missing_evidence_stays_unknown_and_no_recommendation(self):
        result = directions.evaluate(self.store, self.comparison())
        self.assertIsNone(result['recommendation'])
        self.assertTrue(all(c['score_range'] == [0, 5] for c in result['candidates']))
        self.assertTrue(all(c['gate'] == 'conditional' for c in result['candidates']))

    def test_direction_unreviewed_paper_cannot_become_certain_recommendation(self):
        result = directions.evaluate(self.store, self.comparison([self.paper]))
        self.assertIsNone(result['recommendation'])
        self.assertIn(self.paper, result['candidates'][0]['unreviewed_sources'])

    def test_direction_gates_sensitivity_and_no_hypothesis_mutation(self):
        evidence = self.apply(lambda: self.store.add_node('V', 'Reviewed source', {'review_status': 'accepted'}))
        spec = self.comparison([evidence]); before = self.store.get(self.hypothesis)
        result = directions.evaluate(self.store, spec)
        self.assertEqual(result['recommendation'], 'a')
        self.assertTrue(result['sensitivity']['stable'])
        spec['candidates'][0]['hard_constraints'][0]['status'] = 'fail'
        result = self.apply(lambda: directions.save(self.store, spec))
        self.assertNotEqual(result['recommendation'], 'a')
        self.assertEqual(next(c for c in result['candidates'] if c['id']=='a')['gate'], 'blocked')
        self.assertEqual(self.store.get(self.hypothesis), before)

    def test_direction_invalid_or_fake_sources_are_rejected(self):
        spec = self.comparison(['P9999'])
        with self.assertRaises(ResearchError): directions.evaluate(self.store, spec)
        spec = self.comparison();spec['weights'] = {k: float('nan') for k in directions.CRITERIA}
        with self.assertRaises(ResearchError): directions.evaluate(self.store, spec)

    def test_http_origin_validation_and_cli_backed_draft_isolation(self):
        registry = self.root / 'workspace/projects.json'
        server = watch.server(self.root, 0, registry); thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:' + str(server.server_port)
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def get(route):
            with op.open(base+route) as r: return r.read()
        self.assertIn('Lightning'.encode(), get('/lightning'))
        token=json.loads(get('/api/session'))['token']
        data=json.dumps({'action':'start','draft':{'title':'Quick'}}).encode()
        request=urllib.request.Request(base+'/api/lightning',data=data,headers={'Content-Type':'application/json','X-VR-Token':token},method='POST')
        with self.assertRaises(urllib.error.HTTPError) as e: op.open(request)
        self.assertEqual(e.exception.code,403)
        request.add_header('Origin',base)
        with op.open(request) as r: draft=json.load(r)
        self.assertEqual(json.loads(get('/api/lightning'))['drafts'][0]['id'],draft['id'])
        self.assertFalse(registry.exists())
        self.assertEqual(json.loads(get('/api/projects'))['projects'],[])

    def test_draft_conflict_keeps_newer_agent_output(self):
        draft = lightning.write(self.root, title='Initial')
        newer = lightning.write(self.root, draft['id'], output='Agent result')
        with self.assertRaises(ResearchError):
            lightning.write(self.root, draft['id'], expected_updated_at=draft['updated_at'], output='Stale editor')
        self.assertEqual(lightning.show(self.root, draft['id'])['output'], newer['output'])

    def test_http_project_views_and_depth_change(self):
        registry = self.root / 'projects.json'
        project = hub.register(registry, self.store.root, 'Test project')
        server=watch.server(self.root,0,registry);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base='http://127.0.0.1:'+str(server.server_port);prefix='/p/'+project['id']
        op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def get(route):
            with op.open(base+route) as r: return r.read()
        self.assertEqual(len(json.loads(get(prefix+'/api/research/history?topic=method%2Croute'))['events']),2)
        self.assertIn('criteria',json.loads(get(prefix+'/api/research/directions'))['packet'])
        page=get(prefix+'/explore').decode()
        self.assertIn("get('/api/state')",page)
        token=json.loads(get('/api/session'))['token']
        req=urllib.request.Request(base+prefix+'/api/research',data=json.dumps({'action':'reading_depth','id':self.paper,'depth':'skim','reason':'User choice'}).encode(),headers={'Content-Type':'application/json','Origin':base,'X-VR-Token':token},method='POST')
        with op.open(req) as r: self.assertEqual(json.load(r)['depth'],'skim')
        self.assertEqual(self.store.get(self.paper)['data']['reading_depth'],'skim')


if __name__ == '__main__': unittest.main()
