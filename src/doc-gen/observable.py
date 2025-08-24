#!/usr/bin/env python3
"""
Simple Observable Store

A minimal key-value store with async callbacks for agent coordination.
"""

import threading
from typing import Dict, Callable, List
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
    """Simple observable key-value store with async callbacks"""
    
    def __init__(self):
        self._data: TaskStatusDict = TaskStatusDict()
        self._callbacks: List[Callable[[TaskStatusDict], None]] = []
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="callback-")
    
    def subscribe(self, callback: Callable[[TaskStatusDict], None]) -> TaskStatusDict:
        """Subscribe to changes. Returns current state immediately."""
        with self._lock:
            self._callbacks.append(callback)
            return self._data.copy()
    
    def set(self, key: str, value: TaskStatus):
        """Set a key-value pair and notify all subscribers asynchronously"""
        with self._lock:
            self._data[key] = value
            # Create a copy of the data for callbacks
            data_copy = self._data.copy()
            callbacks_copy = self._callbacks.copy()
        
        # Execute callbacks asynchronously to avoid blocking
        for callback in callbacks_copy:
            self._executor.submit(self._safe_callback, callback, data_copy)
    
    def _safe_callback(self, callback: Callable[[TaskStatusDict], None], data: TaskStatusDict):
        """Execute callback safely, removing it if it fails"""
        try:
            callback(data)
        except Exception as e:
            print(f"Warning: Callback error, removing subscriber: {e}")
            # Remove the failed callback
            with self._lock:
                if callback in self._callbacks:
                    self._callbacks.remove(callback)
