#!/usr/bin/env python3
"""
Tests for ObservableStore team-driven subscriptions
"""

import time
import threading
import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observable import ObservableStore, TaskStatus


class FakeTeam:
    def __init__(self):
        self.started_with = None
        self.stopped_with = None
        self.start_event = threading.Event()
        self.stop_event = threading.Event()

    def start(self, agent_ids):
        self.started_with = list(agent_ids)
        self.start_event.set()

    def stop(self, force=False):
        self.stopped_with = bool(force)
        self.stop_event.set()


class TestObservableTeamSubscriptions(unittest.TestCase):

    def test_subscribe_team_ready_triggers_start_when_all_complete(self):
        store = ObservableStore(max_workers=4)
        team = FakeTeam()

        # subscribe which depends on two agent ids
        store.subscribe_team(team, ['a1', 'a2'], trigger='ready', one_shot=True)

        # set first agent to complete (not enough yet)
        store.set('a1', TaskStatus.COMPLETE)
        time.sleep(0.05)
        self.assertFalse(team.start_event.is_set())

        # set second agent to complete -> should trigger start
        store.set('a2', TaskStatus.COMPLETE)

        # wait for executor to run start
        started = team.start_event.wait(timeout=1.0)
        self.assertTrue(started)
        self.assertEqual(set(team.started_with), {'a1', 'a2'})

    def test_subscribe_team_any_error_triggers_stop(self):
        store = ObservableStore(max_workers=4)
        team = FakeTeam()

        store.subscribe_team(team, ['a3'], trigger='any_error', one_shot=True)

        # set agent to error -> should trigger stop
        store.set('a3', TaskStatus.ERROR)

        stopped = team.stop_event.wait(timeout=1.0)
        self.assertTrue(stopped)
        self.assertTrue(team.stopped_with)


if __name__ == '__main__':
    unittest.main()
