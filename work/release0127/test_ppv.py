import sys,time,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE/'stage/plugin.video.stremio.bridge'))
from resources.lib import ppv

class BoxingPPVTests(unittest.TestCase):
    def test_not_other_combat_sports(self):
        self.assertFalse(ppv.boxing({'name':'UFC Main Event'}))
        self.assertFalse(ppv.boxing({'name':'WWE PPV'}))
        self.assertFalse(ppv.boxing({'name':'Football final'}))
        self.assertFalse(ppv.boxing({'name':'SKY SPORTS MAIN EVENT'}))
        self.assertTrue(ppv.boxing({'name':'Fighter A vs Fighter B','genres':['Boxing']}))
    def test_window_is_estimate_not_playback_claim(self):
        self.assertIn('Links expected from about',ppv.status({'startTime':10000},now=1000))
        self.assertIn('window is open',ppv.status({'startTime':10000},now=7000))
        self.assertIn('may have ended',ppv.status({'startTime':10000},now=10001))
    def test_unknown_time_not_invented(self):
        self.assertIn('not supplied',ppv.status({'released':'2026-12-01'}))
        self.assertIn('not supplied',ppv.status({'startTime':'invalid'}))
    def test_timezones_and_milliseconds(self):
        self.assertEqual(ppv.starts({'startTime':'2026-12-01T20:00:00+02:00'}),ppv.starts({'startTime':'2026-12-01T18:00:00Z'}))
        self.assertEqual(ppv.starts({'startTime':1800000000000}),1800000000)
        self.assertEqual(ppv.starts({'description':'28 Nov 2026 · 18:00 UTC'}),ppv.starts({'startTime':'2026-11-28T18:00:00Z'}))
        self.assertIsNone(ppv.starts({'description':'31 Feb 2026 · 18:00 UTC'}))
    def test_primary_provider_ids_deduplicated(self):
        entry={'key':'primary','label':'Primary sports','manifest':{'id':'test.sports'}}
        cats=[{'id':'sports_today','type':'sport'},{'id':'sports_live','type':'sport'}]
        with patch.object(ppv,'entry_catalogs',return_value=cats),patch.object(ppv,'fetch_resource',return_value={'metas':[{'id':'provider:original','name':'Boxing tonight'}]}):
            rows,errors=ppv.events(None,entry)
        self.assertEqual(len(rows),1);self.assertEqual(errors,0)
        self.assertEqual(rows[0]['meta']['id'],'provider:original');self.assertEqual(rows[0]['provider'],'primary')
    def test_failure_reported_not_empty_success(self):
        with patch.object(ppv,'entry_catalogs',return_value=[{'id':'sports_fight','type':'sport'}]),patch.object(ppv,'fetch_resource',side_effect=OSError()):
            rows,errors=ppv.events(None,{})
        self.assertEqual(rows,[]);self.assertEqual(errors,1)

if __name__=='__main__':unittest.main(verbosity=2)
