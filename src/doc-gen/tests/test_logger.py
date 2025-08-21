#!/usr/bin/env python3
"""Tests for simplified logger module with factory pattern."""

import threading
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from logger import (
    ConsoleLogger, MemoryLogger, LogEntry,
    ConsoleLoggerFactory, MemoryLoggerFactory,
    get_default_factory, set_default_factory, get_logger
)


class TestConsoleLogger(unittest.TestCase):
    def test_console_logger_basic(self):
        # Basic test that console logger doesn't crash
        logger = ConsoleLogger()
        logger.log("Test message", "test")
        logger.error("Test error", "test")
        # No assertions - just verify no exceptions


class TestMemoryLogger(unittest.TestCase):
    def test_basic_logging(self):
        logger = MemoryLogger()
        logger.log("Hello", "test")
        logger.error("Oops", "test")
        entries = logger.entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].message, "Hello")
        self.assertEqual(entries[1].is_error, True)
        self.assertEqual(entries[1].message, "Oops")

    def test_thread_safety(self):
        logger = MemoryLogger()
        N = 50
        def worker(idx):
            for i in range(N):
                logger.log(f"w{idx}-{i}", "thread")
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(logger.entries()), 3 * N)

    def test_error_detection(self):
        logger = MemoryLogger()
        logger.log("Normal message", "test")
        self.assertFalse(logger.has_errors())
        
        logger.error("Error message", "test")
        self.assertTrue(logger.has_errors())

    def test_get_messages(self):
        logger = MemoryLogger()
        logger.log("Message 1", "test")
        logger.error("Error 1", "test")
        logger.log("Message 2", "test")
        
        messages = logger.get_messages()
        self.assertEqual(messages, ["Message 1", "Error 1", "Message 2"])

    def test_clear(self):
        logger = MemoryLogger()
        logger.log("test", "test")
        logger.error("test error", "test")
        self.assertEqual(len(logger.entries()), 2)
        
        logger.clear()
        self.assertEqual(len(logger.entries()), 0)
        self.assertFalse(logger.has_errors())


class TestLoggerFactories(unittest.TestCase):
    def test_console_factory(self):
        factory = ConsoleLoggerFactory()
        logger = factory.create_logger("test")
        self.assertIsInstance(logger, ConsoleLogger)

    def test_test_factory(self):
        factory = MemoryLoggerFactory()
        logger1 = factory.create_logger("comp1")
        logger2 = factory.create_logger("comp2")
        # Should return same instance (singleton)
        self.assertIs(logger1, logger2)
        
        logger1.log("test message", "comp1")
        logger1.error("test error", "comp1")
        
        entries = factory.get_entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].message, "test message")
        self.assertEqual(entries[1].is_error, True)
        self.assertTrue(factory.has_errors())
        
        factory.clear()
        self.assertEqual(len(factory.get_entries()), 0)
        self.assertFalse(factory.has_errors())

    def test_global_factory_management(self):
        # Save original factory
        original = get_default_factory()
        
        try:
            # Set test factory
            test_factory = MemoryLoggerFactory()
            set_default_factory(test_factory)
            
            # Use convenience function
            logger = get_logger("global_test")
            logger.log("global test message", "global_test")
            logger.error("global error", "global_test")
            
            entries = test_factory.get_entries()
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].message, "global test message")
            self.assertEqual(entries[0].component, "global_test")
            self.assertTrue(test_factory.has_errors())
        
        finally:
            # Restore original factory
            set_default_factory(original)


class TestLogEntry(unittest.TestCase):
    def test_log_entry_format(self):
        from datetime import datetime
        entry = LogEntry(
            ts=datetime(2025, 1, 1, 12, 30, 45),
            component="test",
            message="test message",
            is_error=False
        )
        formatted = entry.format()
        self.assertIn("12:30:45", formatted)
        self.assertIn("INFO", formatted)
        self.assertIn("test", formatted)
        self.assertIn("test message", formatted)
        
        error_entry = LogEntry(
            ts=datetime(2025, 1, 1, 12, 30, 45),
            component="test",
            message="error message",
            is_error=True
        )
        error_formatted = error_entry.format()
        self.assertIn("ERROR", error_formatted)
        self.assertIn("error message", error_formatted)


if __name__ == "__main__":
    unittest.main()
