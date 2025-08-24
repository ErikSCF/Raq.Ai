#!/usr/bin/env python3
"""Integration test for WorkflowManager with logger factory."""

import unittest
import tempfile
import yaml
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow import WorkflowManager
from workflow_orchestrator import WorkflowOrchestrator
from team_runner import TeamRunnerFactory
from logger import MemoryLoggerFactory, ConsoleLoggerFactory


class TestWorkflowManagerWithLogger(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures with minimal workflow"""
        self.test_workflow_data = {
            'workflow': {
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {
                        'id': 'test_team_001',
                        'template': 'TestTeam.yaml',
                        'output_file': 'test_output.md'
                    },
                    {
                        'id': 'test_team_002', 
                        'template': 'TestTeam2.yaml',
                        'output_file': 'test_output2.md',
                        'depends_on': 'test_team_001'
                    }
                ]
            }
        }
        
        # Create temporary workflow file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(self.test_workflow_data, self.temp_file)
        self.temp_file.close()
        self.workflow_path = self.temp_file.name

    def tearDown(self):
        """Clean up temporary files"""
        try:
            Path(self.workflow_path).unlink()
        except OSError:
            pass

    def test_workflow_with_console_logger(self):
        """Test workflow initialization with console logger (no assertions on output)"""
        factory = ConsoleLoggerFactory()
        wm = WorkflowManager(self.workflow_path, factory)
        
        # This should log to console
        orchestrator = WorkflowOrchestrator()
        wm.initialize(
            job_id="test_001",
            document_type="test",
            output_base_path="/tmp/test_output",
            orchestrator=orchestrator,
            team_runner_factory=TeamRunnerFactory(factory),
            assets=[]
        )
        
        # Basic assertions
        self.assertEqual(len(wm.teams), 2)
        self.assertEqual(wm.teams[0].id, 'test_team_001')
        self.assertEqual(wm.teams[1].id, 'test_team_002')

    def test_workflow_with_test_logger(self):
        """Test workflow initialization with test logger and capture logs"""
        factory = MemoryLoggerFactory()
        wm = WorkflowManager(self.workflow_path, factory)
        
        orchestrator = WorkflowOrchestrator()
        wm.initialize(
            job_id="test_002",
            document_type="test",
            output_base_path="/tmp/test_output",
            orchestrator=orchestrator,
            team_runner_factory=TeamRunnerFactory(factory),
            assets=[]
        )
        
        # Check that teams were created
        self.assertEqual(len(wm.teams), 2)
        
        # Check logged messages
        shared_logger = factory.create_logger()
        entries = shared_logger.entries()
        messages = [entry.message for entry in entries]
        
        # Should have logged job folder creation
        job_folder_msgs = [msg for msg in messages if "Created job output folder" in msg]
        self.assertTrue(len(job_folder_msgs) > 0)
        
        # Should have logged team registrations
        team_reg_msgs = [msg for msg in messages if "registered with observable store" in msg]
        self.assertEqual(len(team_reg_msgs), 2)
        
        # Should have logged workflow initialization
        init_msgs = [msg for msg in messages if "Workflow initialized with" in msg]
        self.assertTrue(len(init_msgs) > 0)
        self.assertIn("Workflow initialized with 2 teams", init_msgs[0])

    def test_error_logging_with_test_logger(self):
        """Test that errors are properly captured by test logger"""
        factory = MemoryLoggerFactory()
        
        # Test with invalid workflow path
        wm = WorkflowManager("/nonexistent/path.yaml", factory)
        
        # This should cause an error during asset loading if we try to initialize
        # For now, just test that the logger factory was set up correctly
        self.assertIsNotNone(wm.logger_factory)
        self.assertIs(wm.logger_factory, factory)
        
        # Test logging an error directly
        wm.logger.error("Test error message")
        
        shared_logger = factory.create_logger()
        entries = shared_logger.entries()
        error_entries = [e for e in entries if e.is_error]
        self.assertEqual(len(error_entries), 1)
        self.assertEqual(error_entries[0].message, "Test error message")
        self.assertTrue(shared_logger.has_errors())


if __name__ == "__main__":
    unittest.main()
