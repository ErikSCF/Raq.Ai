#!/usr/bin/env python3
"""
Workflow Orchestrator

Orchestrates team execution based on dependencies and state management.
A specialized observable store for workflow coordination.
"""

import threading
from typing import Dict, Callable, List, Any, Set, Optional
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from logger import LoggerFactory, get_default_factory, Logger


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


class WorkflowOrchestrator:
    """Orchestrates team execution based on dependencies and state.

    Coordinates team execution by:
    - Tracking team/task status (PENDING -> STARTED -> COMPLETE/ERROR)
    - Managing dependency-based execution triggers
    - Providing thread-safe state management
    - Triggering team starts when dependencies are satisfied
    """

    def __init__(self, max_workers: int = 10, logger_factory: Optional[LoggerFactory] = None):
        self._data: TaskStatusDict = TaskStatusDict()
        # Team subscriptions: list of dicts with keys: team, agent_ids (set), triggered
        self._team_subs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="orchestrator-")
        self._logger_factory = logger_factory or get_default_factory()
        self._logger = self._logger_factory.create_logger("workflow_orchestrator")

    def subscribe_team(self, team: Any, agent_ids: List[str]) -> Callable[[], None]:
        """Subscribe a team with dependent agent ids.

        The team will have start(agent_ids) invoked exactly once when all
        provided agent_ids are COMPLETE. If agent_ids is empty, the team starts
        immediately (as soon as the next set call occurs).

        Returns an unsubscribe function.
        """
        sub = {
            'team': team,
            'agent_ids': set(agent_ids),
            'triggered': False,
        }
        with self._lock:
            self._team_subs.append(sub)

        def unsubscribe():
            with self._lock:
                if sub in self._team_subs:
                    self._team_subs.remove(sub)

        return unsubscribe

    def get(self, key: str) -> TaskStatus:
        """Get the status of a task/team."""
        with self._lock:
            return self._data.get(key, TaskStatus.PENDING)
    
    def set(self, key: str, value: TaskStatus):
        """Set a key-value pair and notify subscribers asynchronously.

        Team subscriptions are evaluated quickly under lock and any long-running
        actions are submitted to the executor.
        """
        with self._lock:
            self._data[key] = value
            # Create copies for evaluation outside the lock
            data_copy = self._data.copy()
            team_subs_copy = [dict(s) for s in self._team_subs]

        # Evaluate team subscriptions quickly and submit long-running actions
        for sub in team_subs_copy:
            try:
                if not sub.get('triggered') and self._dependencies_complete(sub, data_copy):
                    self._executor.submit(self._safe_team_action, sub, 'start', list(sub['agent_ids']), data_copy)
                    with self._lock:
                        for real_sub in self._team_subs:
                            if real_sub is sub or (real_sub['team'] == sub['team'] and real_sub['agent_ids'] == sub['agent_ids']):
                                real_sub['triggered'] = True
                                break
            except Exception as e:
                self._logger.error(f"subscription evaluation error: {e}")

    def _dependencies_complete(self, sub: Dict[str, Any], data: TaskStatusDict) -> bool:
        """Return True when all dependency agent ids are COMPLETE (or none given)."""
        agent_ids: Set[str] = set(sub.get('agent_ids', []))
        if not agent_ids:
            return True
        return all(data.get(a, TaskStatus.PENDING) == TaskStatus.COMPLETE for a in agent_ids)

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
            self._logger.error(f"Team action error for team {getattr(team, 'id', str(team))}: {e}")
            # If team action fails, remove subscription to avoid repeated failures
            with self._lock:
                if sub in self._team_subs:
                    try:
                        self._team_subs.remove(sub)
                    except ValueError:
                        pass
