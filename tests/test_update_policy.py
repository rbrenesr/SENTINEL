import datetime as dt
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('policy', pathlib.Path(__file__).resolve().parents[1] / 'scripts/check_update.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
NOW = dt.datetime(2026, 11, 19, 12, tzinfo=dt.timezone.utc)


class UpdatePolicyTests(unittest.TestCase):
    def snapshot(self, minutes):
        return {'updatedAt': (NOW - dt.timedelta(minutes=minutes)).isoformat(), 'items': [], 'sources': []}

    def test_frequent_schedule_skips_recent_success_but_collects_after_interval(self):
        self.assertFalse(policy.collection_due(self.snapshot(15), 'schedule', NOW)[0])
        self.assertTrue(policy.collection_due(self.snapshot(30), 'schedule', NOW)[0])
        self.assertTrue(policy.collection_due(self.snapshot(500), 'schedule', NOW)[0])

    def test_manual_requests_and_code_changes_always_collect(self):
        for event in ('workflow_dispatch', 'push'):
            self.assertTrue(policy.collection_due(self.snapshot(1), event, NOW)[0])

    def test_invalid_snapshot_or_clock_never_blocks_recovery(self):
        for snapshot in ({}, {'updatedAt': 'invalid'}, self.snapshot(-60), {'updatedAt': NOW.isoformat(),'items':None,'sources':[]}):
            self.assertTrue(policy.collection_due(snapshot, 'schedule', NOW)[0])


if __name__ == '__main__':
    unittest.main()
