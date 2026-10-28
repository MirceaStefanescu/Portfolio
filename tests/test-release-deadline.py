"""Deterministic deadline regressions; never starts Kubernetes or a subprocess."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE = Path(os.environ['RELEASE_CANDIDATE']) if 'RELEASE_CANDIDATE' in os.environ else Path(__file__).resolve().parents[1] / 'scripts/release-environment.py'
spec = importlib.util.spec_from_file_location('release_deadline_candidate', SOURCE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def rollout(phase):
    return json.dumps({'metadata': {'generation': 7},
                       'status': {'observedGeneration': 7, 'phase': phase}})


class DeadlineTests(unittest.TestCase):
    def test_query_receives_remaining_budget(self):
        with patch.object(release.time, 'monotonic', return_value=0), \
                patch.object(release, 'run', return_value=rollout('Healthy')) as command:
            release.wait_canary(['kubectl', '--context', 'synthetic'], 'canary-demo', 10)
        self.assertEqual(command.call_args.kwargs.get('timeout'), 10)

    def test_healthy_response_at_or_after_deadline_is_rejected(self):
        for elapsed in (10, 10.1):
            with self.subTest(elapsed=elapsed):
                clock = [0.0]
                def response(*args, **kwargs):
                    clock[0] = elapsed
                    return rollout('Healthy')
                with patch.object(release.time, 'monotonic', side_effect=lambda: clock[0]), \
                        patch.object(release, 'run', side_effect=response):
                    with self.assertRaisesRegex(TimeoutError, 'deadline'):
                        release.wait_canary(['kubectl'], 'canary-demo', 10)

    def test_sleep_does_not_exceed_remaining_budget(self):
        clock = [0.0]
        def response(*args, **kwargs):
            clock[0] = 9.75
            return rollout('Progressing')
        def advance(seconds):
            clock[0] += seconds
        with patch.object(release.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(release.time, 'sleep', side_effect=advance) as sleep, \
                patch.object(release, 'run', side_effect=response) as command:
            with self.assertRaises(TimeoutError):
                release.wait_canary(['kubectl'], 'canary-demo', 10)
        sleep.assert_called_once_with(0.25)
        self.assertEqual(command.call_count, 1)

    def test_later_query_receives_reduced_budget(self):
        clock = [0.0]
        responses = iter([(2, 'Progressing'), (1, 'Healthy')])
        def response(*args, **kwargs):
            elapsed, phase = next(responses)
            clock[0] += elapsed
            return rollout(phase)
        def advance(seconds):
            clock[0] += seconds
        with patch.object(release.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(release.time, 'sleep', side_effect=advance), \
                patch.object(release, 'run', side_effect=response) as command:
            release.wait_canary(['kubectl'], 'canary-demo', 10)
        self.assertEqual([call.kwargs.get('timeout') for call in command.call_args_list], [10, 6])

    def test_healthy_before_deadline_is_accepted(self):
        clock = [0.0]
        def response(*args, **kwargs):
            clock[0] = 9.9
            return rollout('Healthy')
        with patch.object(release.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(release.time, 'sleep') as sleep, \
                patch.object(release, 'run', side_effect=response):
            self.assertIsNone(release.wait_canary(['kubectl'], 'canary-demo', 10))
        sleep.assert_not_called()

    def test_expired_budget_does_not_issue_query(self):
        with patch.object(release.time, 'monotonic', side_effect=[0, 10]), \
                patch.object(release, 'run') as command:
            with self.assertRaises(TimeoutError):
                release.wait_canary(['kubectl'], 'canary-demo', 10)
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
