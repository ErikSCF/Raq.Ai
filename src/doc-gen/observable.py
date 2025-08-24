#!/usr/bin/env python3
"""
Simple Observable Store

A minimal key-value store with async callbacks for agent coordination.
"""

import threading
from typing import Dict, Any, Callable, List
from concurrent.futures import ThreadPoolExecutor


class ObservableStore:
    """Simple observable key-value store with async callbacks"""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="callback-")
    
    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        """Subscribe to changes. Returns current state immediately."""
        with self._lock:
            self._callbacks.append(callback)
            return self._data.copy()
    
    def set(self, key: str, value: Any):
        """Set a key-value pair and notify all subscribers asynchronously"""
        with self._lock:
            self._data[key] = value
            # Create a copy of the data for callbacks
            data_copy = self._data.copy()
            callbacks_copy = self._callbacks.copy()
        
        # Execute callbacks asynchronously to avoid blocking
        for callback in callbacks_copy:
            self._executor.submit(self._safe_callback, callback, data_copy)
    
    def _safe_callback(self, callback: Callable[[Dict[str, Any]], None], data: Dict[str, Any]):
        """Execute callback safely, removing it if it fails"""
        try:
            callback(data)
        except Exception as e:
            print(f"Warning: Callback error, removing subscriber: {e}")
            # Remove the failed callback
            with self._lock:
                if callback in self._callbacks:
                    self._callbacks.remove(callback)
