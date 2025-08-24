#!/usr/bin/env python3
"""
Simple Observable Store

A minimal key-value store with async callbacks for agent coordination.
"""

import threading
from typing import Dict, Callable, List, Any, Set, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from enum import Enum


class TaskStatus(Enum):
    """Enum for task/team status values"""
    STARTED = "started"
    PENDING = "pending"
    COMPLETE = "complete"
    ERROR = "error"


class TaskStatusDict(Dict[str, TaskStatus]):
    """A specialized dictionary for tracking task/team statuses with helper methods"""

    def copy(self) -> 'TaskStatusDict':
        """Return a copy that preserves the TaskStatusDict type"""
        new_dict = TaskStatusDict()
        new_dict.update(self)
        return new_dict
    
    def has_errors(self, task_id: str) -> bool:
        """Check if a task has errors"""
        return self.get(task_id, TaskStatus.PENDING) == TaskStatus.ERROR
    
    def is_completed(self, task_ids: List[str]) -> bool:
        """Check if all tasks in the list are complete"""
        return all(self.get(task_id, TaskStatus.PENDING) == TaskStatus.COMPLETE for task_id in task_ids)
    
    def all_complete(self) -> bool:
        """Check if all tasks are complete"""
        return len(self) > 0 and all(status == TaskStatus.COMPLETE for status in self.values())


class ObservableStore:
    """Simple observable key-value store with async callbacks and team subscriptions

    This store keeps two types of subscriptions:
    - legacy callbacks (callable taking TaskStatusDict) kept for compatibility
    - team subscriptions registered via `subscribe_team(team, agent_ids, trigger)`

    Team subscriptions are evaluated quickly on updates and, when their trigger
    condition matches, the long-running team action (`team.start` / `team.stop`) is
    submitted to the executor to avoid blocking observable evaluation.
    """

    def __init__(self, max_workers: int = 10):
        self._data: TaskStatusDict = TaskStatusDict()
    # legacy callback list removed - use team subscriptions only
        # Team subscriptions: list of dicts with keys: team, agent_ids (set), trigger, one_shot, triggered
        self._team_subs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="callback-")

    # Legacy callback-style subscription removed. Use `subscribe_team` for
    # team-driven orchestration. This keeps the store focused on declarative
    # subscriptions handled by the workflow.

    def subscribe_team(self, team: Any, agent_ids: List[str], trigger: str = "ready", one_shot: bool = True) -> Callable[[], None]:
        """Subscribe a team with dependent agent ids.

        - team: Team instance (must implement start(agent_ids) and stop(force=False))
        - agent_ids: list of dependent agent ids the team cares about
        - trigger: "ready"|'all_complete' to call team.start when all deps COMPLETE,
                   "any_error" to call team.stop(force=True) when any dep is ERROR
        - one_shot: if True, the subscription is removed after its action fires

        Returns an unsubscribe function.
        """
        sub = {
            'team': team,
            'agent_ids': set(agent_ids),
            'trigger': trigger,
            'one_shot': bool(one_shot),
            'triggered': False,
        }
        with self._lock:
            self._team_subs.append(sub)

        def unsubscribe():
            with self._lock:
                if sub in self._team_subs:
                    self._team_subs.remove(sub)

        return unsubscribe

    def set(self, key: str, value: TaskStatus):
        """Set a key-value pair and notify subscribers asynchronously.

        Team subscriptions are evaluated quickly under lock and any long-running
        actions are submitted to the executor.
        """
        with self._lock:
            self._data[key] = value
            # Create copies for evaluation outside the lock
            data_copy = self._data.copy()
            callbacks_copy = []
            team_subs_copy = [dict(s) for s in self._team_subs]

    # (No legacy callbacks) Team subscriptions drive actions

        # Evaluate team subscriptions quickly and submit long-running actions
        for sub in team_subs_copy:
            try:
                if self._evaluate_subscription_trigger(sub, data_copy):
                    # Submit the appropriate team action to executor
                    if sub['trigger'] in ("ready", "all_complete"):
                        self._executor.submit(self._safe_team_action, sub, 'start', list(sub['agent_ids']), data_copy)
                    elif sub['trigger'] == 'any_error':
                        self._executor.submit(self._safe_team_action, sub, 'stop', True, data_copy)
                    # Mark triggered if one_shot
                    if sub.get('one_shot'):
                        with self._lock:
                            # Find the original sub object and mark/remove it
                            for real_sub in self._team_subs:
                                if real_sub is sub or (real_sub['team'] == sub['team'] and real_sub['agent_ids'] == sub['agent_ids']):
                                    real_sub['triggered'] = True
                                    if real_sub.get('one_shot'):
                                        try:
                                            self._team_subs.remove(real_sub)
                                        except ValueError:
                                            pass
                                    break
            except Exception as e:
                # Any subscription evaluation error should not take down the store
                print(f"Warning: subscription evaluation error: {e}")

    def _evaluate_subscription_trigger(self, sub: Dict[str, Any], data: TaskStatusDict) -> bool:
        """Return True when the subscription's trigger condition is met."""
        trigger = sub.get('trigger', 'ready')
        agent_ids: Set[str] = set(sub.get('agent_ids', []))

        # Empty dependency list means "no deps" -> immediate ready trigger
        if not agent_ids:
            return True if trigger in ("ready", "all_complete") else False

        if trigger in ("ready", "all_complete"):
            # start when all dependencies are COMPLETE
            return all(data.get(a, TaskStatus.PENDING) == TaskStatus.COMPLETE for a in agent_ids)
        if trigger == 'any_error':
            return any(data.get(a, TaskStatus.PENDING) == TaskStatus.ERROR for a in agent_ids)
        # Unknown trigger - do nothing
        return False

    # legacy _safe_callback removed

    def _safe_team_action(self, sub: Dict[str, Any], action: str, arg: Any, data: TaskStatusDict):
        """Execute a team action (start/stop) safely in the executor."""
        team = sub.get('team')
        try:
            if action == 'start':
                # arg is agent_ids list
                team.start(arg)
            elif action == 'stop':
                # arg is force flag
                team.stop(force=bool(arg))
        except Exception as e:
            print(f"Warning: Team action error for team {getattr(team, 'id', str(team))}: {e}")
            # If team action fails, remove subscription to avoid repeated failures
            with self._lock:
                if sub in self._team_subs:
                    try:
                        self._team_subs.remove(sub)
                    except ValueError:
                        pass
