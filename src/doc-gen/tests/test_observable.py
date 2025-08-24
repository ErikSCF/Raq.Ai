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

from observable import ObservableStore, TaskStatus


class TestObservableStore(unittest.TestCase):
    
    def setUp(self):
        self.store = ObservableStore()
    
    def test_basic_set_and_subscribe(self):
        """Test basic set and subscribe functionality"""
        # Subscribe first
        callback_mock = Mock()
        initial_state = self.store.subscribe(callback_mock)
        
        # Should start empty
        self.assertEqual(initial_state, {})
        
        # Set a value
        self.store.set("key1", TaskStatus.STARTED)
        
        # Give async callback time to execute
        time.sleep(0.1)
        
        # Check callback was called with the data
        callback_mock.assert_called_with({"key1": TaskStatus.STARTED})
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers get notified"""
        callback1 = Mock()
        callback2 = Mock()
        
        # Subscribe both
        self.store.subscribe(callback1)
        self.store.subscribe(callback2)
        
        # Set a value
        self.store.set("test", TaskStatus.PENDING)
        
        # Give time for async callbacks
        time.sleep(0.1)
        
        # Both should be called
        callback1.assert_called_once()
        callback2.assert_called_once()
        
        # Both should get the same data
        call_args1 = callback1.call_args[0][0]
        call_args2 = callback2.call_args[0][0]
        self.assertEqual(call_args1, call_args2)
        self.assertEqual(call_args1["test"], TaskStatus.PENDING)
    
    def test_subscribe_returns_current_state(self):
        """Test that subscribe returns current state immediately"""
        # Set some initial data
        self.store.set("existing", TaskStatus.STARTED)
        
        # Give time for internal processing
        time.sleep(0.05)
        
        # New subscriber should get current state immediately
        callback_mock = Mock()
        current_state = self.store.subscribe(callback_mock)
        
        # Should get current state back
        self.assertEqual(current_state, {"existing": TaskStatus.STARTED})
    
    def test_multiple_values(self):
        """Test setting multiple values"""
        callback_mock = Mock()
        self.store.subscribe(callback_mock)
        
        # Set multiple values
        self.store.set("key1", TaskStatus.STARTED)
        self.store.set("key2", TaskStatus.PENDING)
        self.store.set("key3", TaskStatus.COMPLETE)
        
        # Give time for async callbacks
        time.sleep(0.1)
        
        # Should have been called multiple times
        self.assertEqual(callback_mock.call_count, 3)
        
        # Last call should have all data
        last_call_args = callback_mock.call_args[0][0]
        self.assertEqual(last_call_args["key1"], TaskStatus.STARTED)
        self.assertEqual(last_call_args["key2"], TaskStatus.PENDING)
        self.assertEqual(last_call_args["key3"], TaskStatus.COMPLETE)
    
    def test_update_existing_key(self):
        """Test updating an existing key"""
        callback_mock = Mock()
        self.store.subscribe(callback_mock)
        
        # Set initial value
        self.store.set("key", TaskStatus.PENDING)
        
        # Update the value
        self.store.set("key", TaskStatus.COMPLETE)
        
        # Give time for async callbacks
        time.sleep(0.1)
        
        # Should have been called twice
        self.assertEqual(callback_mock.call_count, 2)
        
        # Last call should have updated value
        last_call_args = callback_mock.call_args[0][0]
        self.assertEqual(last_call_args["key"], TaskStatus.COMPLETE)
    
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
        self.store.set("test", TaskStatus.ERROR)
        
        # Give time for async callbacks and cleanup
        time.sleep(0.2)
        
        # Working callback should have been called
        working_callback.assert_called_once()
        
        # Reset the working callback and set another value
        working_callback.reset_mock()
        self.store.set("test2", TaskStatus.COMPLETE)
        
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
            statuses = [TaskStatus.STARTED, TaskStatus.PENDING, TaskStatus.COMPLETE, TaskStatus.ERROR]
            for i in range(start_index, start_index + 5):
                status = statuses[i % len(statuses)]
                self.store.set(f"key_{i}", status)
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
        statuses = [TaskStatus.STARTED, TaskStatus.PENDING, TaskStatus.COMPLETE, TaskStatus.ERROR]
        for i in range(10):
            self.assertIn(f"key_{i}", last_result)
            expected_status = statuses[i % len(statuses)]
            self.assertEqual(last_result[f"key_{i}"], expected_status)


class TestObservableStoreUsagePatterns(unittest.TestCase):
    """Test common usage patterns for the observable store"""
    
    def setUp(self):
        self.store = ObservableStore()
    
    def test_agent_status_tracking(self):
        """Test using store for agent status tracking"""
        status_changes = []
        
        def track_status(data):
            status_changes.append(data.copy())
        
        # Subscribe to changes
        self.store.subscribe(track_status)
        
        # Simulate agent lifecycle
        self.store.set("agent1", TaskStatus.PENDING)
        self.store.set("agent2", TaskStatus.PENDING)
        self.store.set("agent1", TaskStatus.STARTED)
        self.store.set("agent1", TaskStatus.COMPLETE)
        self.store.set("agent2", TaskStatus.STARTED)
        self.store.set("agent2", TaskStatus.COMPLETE)
        
        # Give time for callbacks
        time.sleep(0.1)
        
        # Should have tracked all status changes
        self.assertEqual(len(status_changes), 6)
        self.assertEqual(status_changes[0]["agent1"], TaskStatus.PENDING)
        self.assertEqual(status_changes[-1]["agent2"], TaskStatus.COMPLETE)
        self.assertEqual(status_changes[-1]["agent1"], TaskStatus.COMPLETE)
    
    def test_workflow_progress_tracking(self):
        """Test using store for workflow progress tracking"""
        progress_updates = []
        
        def track_progress(data):
            progress_updates.append(data.copy())
        
        self.store.subscribe(track_progress)
        
        # Simulate workflow progress with step statuses
        self.store.set("step1", TaskStatus.COMPLETE)
        self.store.set("step2", TaskStatus.COMPLETE)  
        self.store.set("step3", TaskStatus.STARTED)
        self.store.set("step3", TaskStatus.COMPLETE)
        self.store.set("step4", TaskStatus.ERROR)
        
        # Give time for callbacks
        time.sleep(0.1)
        
        self.assertEqual(len(progress_updates), 5)
        self.assertEqual(progress_updates[0]["step1"], TaskStatus.COMPLETE)
        self.assertEqual(progress_updates[-1]["step4"], TaskStatus.ERROR)
        self.assertEqual(progress_updates[-1]["step3"], TaskStatus.COMPLETE)


if __name__ == "__main__":
    unittest.main()
