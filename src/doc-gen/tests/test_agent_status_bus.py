#!/usr/bin/env python3
"""
Tests for Observable Store

Test-driven development for the simple observable key-value store.
"""

import unittest
import threading
import time
import sys
import os
from unittest.mock import Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observable import ObservableStore


class TestObservableStore(unittest.TestCase):
    
    def setUp(self):
        self.store = ObservableStore()
    
    def test_basic_set_and_subscribe(self):
        """Test basic set and subscribe functionality"""
        # Subscribe first
        callback_mock = Mock()
        initial_state = self.store.subscribe(callback_mock)
        
        # Initial state should be empty
        self.assertEqual(initial_state, {})
        
        # Set a value - should trigger callback
        self.store.set("key1", "value1")
        
        # Give time for async callback
        time.sleep(0.1)
        
        # Callback should have been called with the data
        callback_mock.assert_called_once()
        call_args = callback_mock.call_args[0][0]
        self.assertEqual(call_args["key1"], "value1")
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers get notified"""
        callback1 = Mock()
        callback2 = Mock()
        
        # Subscribe both
        self.store.subscribe(callback1)
        self.store.subscribe(callback2)
        
        # Set a value
        self.store.set("test", "data")
        
        # Give time for async callbacks
        time.sleep(0.1)
        
        # Both should be called
        callback1.assert_called_once()
        callback2.assert_called_once()
        
        # Both should get the same data
        call_args1 = callback1.call_args[0][0]
        call_args2 = callback2.call_args[0][0]
        self.assertEqual(call_args1, call_args2)
        self.assertEqual(call_args1["test"], "data")
    
    def test_subscribe_returns_current_state(self):
        """Test that subscribe returns current state immediately"""
        # Set some initial data
        self.store.set("existing", "data")
        
        # Give time for internal processing
        time.sleep(0.05)
        
        # New subscriber should get current state immediately
        callback_mock = Mock()
        current_state = self.store.subscribe(callback_mock)
        
        self.assertEqual(current_state["existing"], "data")
    
    def test_multiple_values(self):
        """Test setting multiple values"""
        callback_mock = Mock()
        self.store.subscribe(callback_mock)
        
        # Set multiple values
        self.store.set("key1", "value1")
        self.store.set("key2", "value2")
        self.store.set("key3", {"nested": "object"})
        
        # Give time for async callbacks
        time.sleep(0.1)
        
        # Should have been called multiple times
        self.assertEqual(callback_mock.call_count, 3)
        
        # Last call should have all data
        last_call_args = callback_mock.call_args[0][0]
        self.assertEqual(last_call_args["key1"], "value1")
        self.assertEqual(last_call_args["key2"], "value2")
        self.assertEqual(last_call_args["key3"]["nested"], "object")
    
    def test_update_existing_key(self):
        """Test updating an existing key"""
        callback_mock = Mock()
        self.store.subscribe(callback_mock)
        
        # Set initial value
        self.store.set("key", "initial")
        
        # Update the value
        self.store.set("key", "updated")
        
        # Give time for async callbacks
        time.sleep(0.1)
        
        # Should have been called twice
        self.assertEqual(callback_mock.call_count, 2)
        
        # Last call should have updated value
        last_call_args = callback_mock.call_args[0][0]
        self.assertEqual(last_call_args["key"], "updated")
    
    def test_callback_failure_removal(self):
        """Test that failed callbacks are automatically removed"""
        # Create a callback that will fail
        def failing_callback(data):
            raise Exception("Callback failed")
        
        working_callback = Mock()
        
        # Subscribe both callbacks
        self.store.subscribe(failing_callback)
        self.store.subscribe(working_callback)
        
        # Set a value - should trigger both callbacks
        self.store.set("test", "data")
        
        # Give time for async callbacks and cleanup
        time.sleep(0.2)
        
        # Working callback should have been called
        working_callback.assert_called_once()
        
        # Reset the working callback and set another value
        working_callback.reset_mock()
        self.store.set("test2", "data2")
        
        # Give time for async callbacks
        time.sleep(0.1)
        
        # Working callback should still be called (failed one removed)
        working_callback.assert_called_once()
    
    def test_thread_safety(self):
        """Test thread safety of the store"""
        results = []
        
        def callback(data):
            results.append(data.copy())
        
        self.store.subscribe(callback)
        
        def set_values(start_index):
            for i in range(start_index, start_index + 5):
                self.store.set(f"key_{i}", f"value_{i}")
                time.sleep(0.01)
        
        # Run operations in parallel
        thread1 = threading.Thread(target=set_values, args=(0,))
        thread2 = threading.Thread(target=set_values, args=(5,))
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Give time for all callbacks to complete
        time.sleep(0.2)
        
        # Should have received multiple callback calls
        self.assertGreater(len(results), 5)
        
        # Last result should have all 10 keys
        last_result = results[-1]
        for i in range(10):
            self.assertIn(f"key_{i}", last_result)
            self.assertEqual(last_result[f"key_{i}"], f"value_{i}")


class TestObservableStoreUsagePatterns(unittest.TestCase):
    """Test common usage patterns for the observable store"""
    
    def setUp(self):
        self.store = ObservableStore()
    
    def test_agent_status_tracking(self):
        """Test using store for agent status tracking"""
        status_changes = []
        
        def track_status(data):
            if "agent_status" in data:
                status_changes.append(data["agent_status"].copy())
        
        # Subscribe to changes
        self.store.subscribe(track_status)
        
        # Simulate agent lifecycle
        self.store.set("agent_status", {"agent1": "pending"})
        self.store.set("agent_status", {"agent1": "running", "agent2": "pending"})
        self.store.set("agent_status", {"agent1": "completed", "agent2": "running"})
        self.store.set("agent_status", {"agent1": "completed", "agent2": "completed"})
        
        # Give time for callbacks
        time.sleep(0.1)
        
        # Should have tracked all status changes
        self.assertEqual(len(status_changes), 4)
        self.assertEqual(status_changes[0]["agent1"], "pending")
        self.assertEqual(status_changes[-1]["agent2"], "completed")
    
    def test_workflow_progress_tracking(self):
        """Test using store for workflow progress"""
        progress_updates = []
        
        def track_progress(data):
            if "workflow_progress" in data:
                progress_updates.append(data["workflow_progress"])
        
        self.store.subscribe(track_progress)
        
        # Simulate workflow progress
        self.store.set("workflow_progress", {"completed_steps": 0, "total_steps": 5})
        self.store.set("workflow_progress", {"completed_steps": 2, "total_steps": 5})
        self.store.set("workflow_progress", {"completed_steps": 5, "total_steps": 5})
        
        # Give time for callbacks
        time.sleep(0.1)
        
        self.assertEqual(len(progress_updates), 3)
        self.assertEqual(progress_updates[0]["completed_steps"], 0)
        self.assertEqual(progress_updates[-1]["completed_steps"], 5)


if __name__ == "__main__":
    unittest.main()
