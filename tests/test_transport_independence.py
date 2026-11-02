"""Exercise store-free probes through the real provider transport boundary."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/vibe-research/runtime'))
from vr import integrations, literature, request_gate
from vr.store import Store

class ProbeTransport(unittest.TestCase):
    def test_real_probe_transport_needs_no_store_and_obeys_shared_budget(self):
        class Response(io.BytesIO):
            status=200
            headers={}
        with patch.object(Store,'init',side_effect=AssertionError('No research project allowed')), \
             patch.object(request_gate,'admit') as admit, \
             patch.object(literature,'credential',return_value=(None,'not_configured')), \
             patch.object(literature.network_access,'decision',return_value={'route':'direct','reason':'fixture'}), \
             patch.object(literature.network_access,'open_request',return_value=Response(b'{"message":{"items":[],"total-results":0}}')) as opened:
            result=integrations.preflight(['crossref'])
        self.assertEqual(result['providers'][0]['status'],'passed')
        self.assertFalse(result['providers'][0]['diagnostic']['cached'])
        admit.assert_called_once_with('crossref',50)
        self.assertEqual(opened.call_count,1)
    def test_shared_budget_deferral_does_not_make_network_request(self):
        with patch.object(request_gate,'admit',side_effect=request_gate.Deferred(9999999999,'budget')), \
             patch.object(literature,'credential',return_value=(None,'not_configured')), \
             patch.object(literature.network_access,'decision',return_value={'route':'direct','reason':'fixture'}), \
             patch.object(literature.network_access,'open_request') as opened:
            result=integrations.preflight(['crossref'])
        self.assertEqual(result['providers'][0]['status'],'waiting')
        opened.assert_not_called()
    def test_offline_store_free_client_cannot_claim_a_cache_hit(self):
        with self.assertRaisesRegex(literature.ResearchError,'离线缓存未命中'):
            literature.Router(offline=True).request('crossref','https://api.crossref.org/works',{})

if __name__=='__main__':unittest.main()
