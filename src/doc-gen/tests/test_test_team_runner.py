#!/usr/bin/env python3
"""Tests for MockTeamRunner and test-specific TeamConfig properties."""

import unittest
import time
from unittest.mock import Mock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team import TeamConfig, Team
from test_team_runner import MockTeamRunner, MockTeamRunnerFactory
from logger import MemoryLoggerFactory


class TestTeamConfigProperties(unittest.TestCase):
    """Test the new test-specific properties in TeamConfig."""
    
    def test_team_config_with_test_properties(self):
        """Test that TeamConfig accepts test-specific properties."""
        config = TeamConfig(
            id="test_001",
            template="TestTemplate.yaml",
            output_file="output.md",
            depends_on=None,
            input_files=[],
            step_files=[],
            agent_result=None,
            model="gpt-4o-mini",
            temperature=0.3,
            max_messages=10,
            allow_repeated_speaker=False,
            max_selector_attempts=3,
            termination_keyword="TERMINATE",
            # Test properties
            test_delay_seconds=0.1,
            test_failure_mode="exception",
            test_failure_delay=0.05,
            test_failure_message="Custom test failure",
            test_success_probability=0.8,
            test_progress_steps=3,
            test_partial_output=True
        )
        
        self.assertEqual(config.id, "test_001")
        self.assertEqual(config.test_delay_seconds, 0.1)
        self.assertEqual(config.test_failure_mode, "exception")
        self.assertEqual(config.test_failure_delay, 0.05)
        self.assertEqual(config.test_failure_message, "Custom test failure")
        self.assertEqual(config.test_success_probability, 0.8)
        self.assertEqual(config.test_progress_steps, 3)
        self.assertTrue(config.test_partial_output)


class TestMockTeamRunner(unittest.TestCase):
    """Test the MockTeamRunner functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.logger_factory = MemoryLoggerFactory()
        self.logger = self.logger_factory.create_logger()
    
    def create_test_config(self, **test_kwargs):
        """Helper to create TeamConfig with test properties."""
        base_config = {
            "id": "test_team",
            "template": "TestTemplate.yaml",
            "output_file": "output.md",
            "depends_on": None,
            "input_files": [],
            "step_files": [],
            "agent_result": None,
            "model": "gpt-4o-mini",
            "temperature": 0.3,
            "max_messages": 10,
            "allow_repeated_speaker": False,
            "max_selector_attempts": 3,
            "termination_keyword": "TERMINATE"
        }
        base_config.update(test_kwargs)
        return TeamConfig(**base_config)
    
    def test_successful_run_with_delay(self):
        """Test successful run with delay and progress steps."""
        config = self.create_test_config(
            test_delay_seconds=0.05,  # Short delay for test
            test_progress_steps=3
        )
        
        runner = MockTeamRunner(config, self.logger)
        
        start_time = time.time()
        runner.run()
        end_time = time.time()
        
        # Should have taken at least the delay time
        self.assertGreaterEqual(end_time - start_time, 0.04)  # Allow for timing variance
        
        # Check progress
        progress = runner.get_progress()
        self.assertEqual(progress["team_id"], "test_team")
        self.assertEqual(progress["current_step"], 3)
        self.assertEqual(progress["total_steps"], 3)
        self.assertEqual(progress["percentage"], 100.0)
        self.assertFalse(progress["running"])
        
        # Check logged messages
        entries = self.logger.entries()
        messages = [e.message for e in entries]
        
        self.assertAny(lambda msg: "Starting test run for team test_team" in msg, messages)
        self.assertAny(lambda msg: "Progress 1/3" in msg, messages)
        self.assertAny(lambda msg: "Progress 2/3" in msg, messages)
        self.assertAny(lambda msg: "Progress 3/3" in msg, messages)
        self.assertAny(lambda msg: "Completed successfully" in msg, messages)
    
    def test_exception_failure_mode(self):
        """Test that exception failure mode raises RuntimeError."""
        config = self.create_test_config(
            test_failure_mode="exception",
            test_failure_message="Test exception message"
        )
        
        runner = MockTeamRunner(config, self.logger)
        
        with self.assertRaises(RuntimeError) as cm:
            runner.run()
        
        self.assertIn("Test exception for team test_team", str(cm.exception))
        self.assertIn("Test exception message", str(cm.exception))
        
        # Check error logging
        entries = self.logger.entries()
        error_entries = [e for e in entries if e.is_error]
        self.assertTrue(len(error_entries) > 0)
        self.assertAny(lambda msg: "Raising exception" in msg, 
                      [e.message for e in error_entries])
    
    def test_timeout_failure_mode(self):
        """Test timeout failure mode logs but doesn't raise."""
        config = self.create_test_config(
            test_failure_mode="timeout",
            test_failure_message="Timeout occurred"
        )
        
        runner = MockTeamRunner(config, self.logger)
        
        # Should not raise exception
        runner.run()
        
        # Check timeout logging
        entries = self.logger.entries()
        error_entries = [e for e in entries if e.is_error]
        self.assertTrue(len(error_entries) > 0)
        self.assertAny(lambda msg: "Simulating timeout" in msg and "Timeout occurred" in msg,
                      [e.message for e in error_entries])
    
    def test_partial_failure_mode(self):
        """Test partial failure mode with partial output."""
        config = self.create_test_config(
            test_failure_mode="partial_failure",
            test_partial_output=True,
            test_failure_message="Partial failure occurred"
        )
        
        runner = MockTeamRunner(config, self.logger)
        runner.run()
        
        # Check partial failure logging
        entries = self.logger.entries()
        messages = [e.message for e in entries]
        error_entries = [e for e in entries if e.is_error]
        
        self.assertAny(lambda msg: "Partial failure" in msg and "Partial failure occurred" in msg,
                      [e.message for e in error_entries])
        self.assertAny(lambda msg: "Some work completed before failure" in msg, messages)
    
    def test_failure_during_progress(self):
        """Test failure that occurs during progress steps."""
        config = self.create_test_config(
            test_delay_seconds=0.1,
            test_progress_steps=4,
            test_failure_delay=0.05,  # Fail halfway through
            test_failure_mode="timeout",
            test_partial_output=True
        )
        
        runner = MockTeamRunner(config, self.logger)
        runner.run()
        
        # Should have made some progress before failing
        progress = runner.get_progress()
        self.assertGreater(progress["current_step"], 0)
        self.assertLess(progress["current_step"], 4)  # Shouldn't complete all steps
        
        # Check logging
        entries = self.logger.entries()
        messages = [e.message for e in entries]
        
        self.assertAny(lambda msg: "Generated partial output before failure" in msg, messages)
        self.assertAny(lambda msg: "Progress" in msg, messages)
    
    def test_success_probability_always_succeed(self):
        """Test success probability of 1.0 (always succeed)."""
        config = self.create_test_config(
            test_success_probability=1.0
        )
        
        runner = MockTeamRunner(config, self.logger)
        
        # Should always succeed
        runner.run()
        
        entries = self.logger.entries()
        messages = [e.message for e in entries]
        self.assertAny(lambda msg: "Completed successfully" in msg, messages)
    
    def test_success_probability_always_fail(self):
        """Test success probability of 0.0 (always fail)."""
        config = self.create_test_config(
            test_success_probability=0.0
        )
        
        runner = MockTeamRunner(config, self.logger)
        runner.run()
        
        # Should have failed
        entries = self.logger.entries()
        error_entries = [e for e in entries if e.is_error]
        self.assertTrue(len(error_entries) > 0)
        self.assertAny(lambda msg: "Random failure (flaky test)" in msg,
                      [e.message for e in error_entries])


class TestMockTeamRunnerFactory(unittest.TestCase):
    """Test the MockTeamRunnerFactory."""
    
    def test_factory_creates_test_runner(self):
        """Test that factory creates MockTeamRunner instances."""
        logger_factory = MemoryLoggerFactory()
        factory = MockTeamRunnerFactory(logger_factory)
        
        # Create a mock team with config
        mock_team = Mock()
        mock_team.config = TeamConfig(
            id="factory_test",
            template="Test.yaml",
            output_file="output.md",
            depends_on=None,
            input_files=[],
            step_files=[],
            agent_result=None,
            model="gpt-4o-mini",
            temperature=0.3,
            max_messages=10,
            allow_repeated_speaker=False,
            max_selector_attempts=3,
            termination_keyword="TERMINATE"
        )
        
        runner = factory.create(mock_team)
        
        self.assertIsInstance(runner, MockTeamRunner)
        self.assertEqual(runner.team_config.id, "factory_test")
        self.assertIsNotNone(runner.logger)
    
    def test_factory_without_logger_factory(self):
        """Test factory works without logger factory."""
        factory = MockTeamRunnerFactory()
        
        mock_team = Mock()
        mock_team.config = TeamConfig(
            id="no_logger_test",
            template="Test.yaml",
            output_file="output.md",
            depends_on=None,
            input_files=[],
            step_files=[],
            agent_result=None,
            model="gpt-4o-mini",
            temperature=0.3,
            max_messages=10,
            allow_repeated_speaker=False,
            max_selector_attempts=3,
            termination_keyword="TERMINATE"
        )
        
        runner = factory.create(mock_team)
        
        self.assertIsInstance(runner, MockTeamRunner)
        self.assertIsNone(runner.logger)


class TestIntegrationWithTeam(unittest.TestCase):
    """Test integration between Team and MockTeamRunner."""
    
    def test_team_with_test_runner_factory(self):
        """Test using MockTeamRunnerFactory with Team class."""
        logger_factory = MemoryLoggerFactory()
        
        config = TeamConfig(
            id="integration_test",
            template="IntegrationTest.yaml",
            output_file="integration_output.md",
            depends_on=None,
            input_files=[],
            step_files=[],
            agent_result=None,
            model="gpt-4o-mini",
            temperature=0.3,
            max_messages=10,
            allow_repeated_speaker=False,
            max_selector_attempts=3,
            termination_keyword="TERMINATE",
            # Test properties
            test_delay_seconds=0.01,
            test_progress_steps=2
        )
        
        team = Team(config, logger_factory)
        test_runner_factory = MockTeamRunnerFactory(logger_factory)
        
        # Create and run the test runner
        runner = test_runner_factory.create(team)
        runner.run()
        
        # Verify it worked
        progress = runner.get_progress()
        self.assertEqual(progress["team_id"], "integration_test")
        self.assertEqual(progress["current_step"], 2)
        self.assertFalse(progress["running"])


# Helper assertion method
def assertAny(self, predicate, iterable):
    """Assert that predicate returns True for at least one item in iterable."""
    if not any(predicate(item) for item in iterable):
        self.fail(f"No item in {list(iterable)} satisfies the predicate")

# Add the helper method to unittest.TestCase
unittest.TestCase.assertAny = assertAny


if __name__ == "__main__":
    unittest.main()
