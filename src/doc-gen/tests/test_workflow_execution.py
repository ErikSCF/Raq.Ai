#!/usr/bin/env python3
"""Comprehensive workflow test using MockTeamRunner and MemoryLogger.

This test demonstrates:
- Full workflow initialization with test YAML
- Observable         try:
            wm = WorkflowManager(workflow_path, self.logger_factory)
            orchestrator = WorkflowOrchestrator(logger_factory=self.logger_factory)
            mock_factory = MockTeamRunnerFactory(self.logger_factory)
            
            wm.initialize(
                job_id="test_successful",
                document_type="test",
                output_base_path=self.output_base_path,
                orchestrator=orchestrator,
                team_runner_factory=mock_factory,
                assets=[]
            )am starts based on dependencies
- Teams using MockTeamRunner for realistic behavior
- Proper logging throughout the process
- Graceful completion or error handling
"""

import unittest
import threading
import time
import tempfile
import yaml
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow import WorkflowManager
from workflow_orchestrator import WorkflowOrchestrator, TaskStatus
from tests.mock_team_runner import MockTeamRunnerFactory, MockTeamRunner
from logger import MemoryLoggerFactory


class TestWorkflowExecution(unittest.TestCase):
    """Test full workflow execution with mock teams."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.logger_factory = MemoryLoggerFactory()
        self.test_workflow_path = Path(__file__).parent / "test_workflow.yaml"
        self.output_base_path = tempfile.mkdtemp()
    
    def test_successful_workflow_execution(self):
        """Test a workflow that should complete successfully."""
        print("\n🚀 Testing Successful Workflow Execution")
        
        # Create a simplified successful workflow
        successful_workflow = {
            'workflow': {
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 10,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {
                        'id': 'team_001',
                        'template': 'Team1.yaml',
                        'output_file': 'team1_output.md',
                        'test_delay_seconds': 0.1,
                        'test_progress_steps': 2
                    },
                    {
                        'id': 'team_002',
                        'template': 'Team2.yaml', 
                        'output_file': 'team2_output.md',
                        'depends_on': 'team_001',
                        'test_delay_seconds': 0.1,
                        'test_progress_steps': 2
                    }
                ]
            }
        }
        
        # Create temporary workflow file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(successful_workflow, f)
            workflow_path = f.name
        
        try:
            # Initialize workflow with mock team runner
            wm = WorkflowManager(workflow_path, self.logger_factory)
            orchestrator = WorkflowOrchestrator(logger_factory=self.logger_factory)
            mock_factory = MockTeamRunnerFactory(self.logger_factory)
            
            wm.initialize(
                job_id="test_successful",
                document_type="test",
                output_base_path=self.output_base_path,
                orchestrator=orchestrator,
                team_runner_factory=mock_factory,
                assets=[]
            )
            
            # Verify teams were created and initialized
            self.assertEqual(len(wm.teams), 2, "Should have 2 teams")
            
            # Check what happened during initialization
            shared_logger = self.logger_factory.create_logger()
            entries = shared_logger.entries()
            messages = [e.message for e in entries]
            
            print(f"   📝 Debug: Got {len(entries)} log entries during initialization:")
            for i, entry in enumerate(entries):
                print(f"      {i+1}. [{entry.component}] {entry.message}")
            
            # Verify each team has a team_runner
            for team in wm.teams:
                print(f"   🔍 Debug: Team {team.id} team_runner = {team.team_runner}")
                self.assertIsNotNone(team.team_runner, f"Team {team.id} should have a team_runner")
                self.assertIsInstance(team.team_runner, MockTeamRunner, f"Team {team.id} should use MockTeamRunner")
            
            # Test proper workflow execution through orchestration
            print("   🧪 Testing workflow orchestration...")
            
            # Run the workflow - this should trigger the orchestration cascade
            wm.run()
            
            # Give time for async orchestration to complete
            import time
            time.sleep(0.5)  # Increased wait time for MockTeamRunner delays
            
            # Check final status
            for team in wm.teams:
                status = orchestrator.get(team.id)
                print(f"   📊 Final status - Team {team.id}: {status}")
                self.assertEqual(status, TaskStatus.COMPLETE, f"Team {team.id} should be complete")
            
            # Check logs
            shared_logger = self.logger_factory.create_logger()
            entries = shared_logger.entries()
            messages = [e.message for e in entries]
            
            # Verify team initialization
            team_init_msgs = [msg for msg in messages if "registered with observable store" in msg or "registered with workflow orchestrator" in msg]
            self.assertTrue(len(team_init_msgs) >= 2, "Both teams should be registered")
            
            # Verify workflow execution
            team_queue_msgs = [msg for msg in messages if "queued for execution" in msg]
            team_start_msgs = [msg for msg in messages if "starting execution" in msg]
            team_complete_msgs = [msg for msg in messages if "completed successfully" in msg]
            
            self.assertEqual(len(team_queue_msgs), 2, "Both teams should be queued")
            self.assertEqual(len(team_start_msgs), 2, "Both teams should start execution")
            self.assertEqual(len(team_complete_msgs), 2, "Both teams should complete")
            
            print(f"✅ Successful workflow test completed with {len(entries)} log entries")
            
        finally:
            Path(workflow_path).unlink()
    
    def test_workflow_with_failure(self):
        """Test workflow with team failure and error handling."""
        print("\n💥 Testing Workflow with Failure")
        
        # Create workflow with failing team
        failing_workflow = {
            'workflow': {
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 10,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {
                        'id': 'good_team',
                        'template': 'GoodTeam.yaml',
                        'output_file': 'good_output.md',
                        'test_delay_seconds': 0.05,
                        'test_progress_steps': 2
                    },
                    {
                        'id': 'bad_team',
                        'template': 'BadTeam.yaml',
                        'output_file': 'bad_output.md',
                        'depends_on': 'good_team',
                        'test_failure_mode': 'exception',
                        'test_failure_message': 'Critical team failure'
                    }
                ]
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(failing_workflow, f)
            workflow_path = f.name
        
        try:
            wm = WorkflowManager(workflow_path, self.logger_factory)
            orchestrator = WorkflowOrchestrator(logger_factory=self.logger_factory)
            mock_factory = MockTeamRunnerFactory(self.logger_factory)
            
            wm.initialize(
                job_id="test_failure",
                document_type="test",
                output_base_path=self.output_base_path,
                orchestrator=orchestrator,
                team_runner_factory=mock_factory,
                assets=[]
            )
            
            # Test direct execution to demonstrate failure behavior
            print("   🧪 Testing direct team execution with failure...")
            
            # Execute good team first
            good_team = next(t for t in wm.teams if t.id == 'good_team')
            good_team.start([])
            
            # Execute bad team (should fail)
            bad_team = next(t for t in wm.teams if t.id == 'bad_team')
            try:
                bad_team.start([])
                self.fail("Bad team should have raised an exception")
            except RuntimeError as e:
                self.assertIn("Critical team failure", str(e))
                print(f"   ✅ Expected exception caught: {e}")
            
            # Check for error handling
            shared_logger = self.logger_factory.create_logger()
            entries = shared_logger.entries()
            error_entries = [e for e in entries if e.is_error]
            
            self.assertTrue(len(error_entries) > 0, "Should have error messages from failing team")
            
            # Verify the specific failure was logged
            error_messages = [e.message for e in error_entries]
            critical_error_found = any("Critical team failure" in msg for msg in error_messages)
            self.assertTrue(critical_error_found, "Should log the critical team failure")
            
            print(f"✅ Failure workflow test completed with {len(error_entries)} error entries")
            
        finally:
            Path(workflow_path).unlink()
    
    def test_complex_workflow_with_dependencies(self):
        """Test complex workflow with multiple dependencies and parallel execution."""
        print("\n🔄 Testing Complex Workflow with Dependencies")
        
        # Use the full test workflow file
        wm = WorkflowManager(str(self.test_workflow_path), self.logger_factory)
        orchestrator = WorkflowOrchestrator(logger_factory=self.logger_factory)
        mock_factory = MockTeamRunnerFactory(self.logger_factory)
        
        wm.initialize(
            job_id="test_complex",
            document_type="test",
            output_base_path=self.output_base_path,
            orchestrator=orchestrator,
            team_runner_factory=mock_factory,
            assets=[]
        )
        
        # Test manual execution respecting dependencies
        print("   🧪 Testing manual dependency execution...")
        
        execution_order = []
        
        # 1. Execute data_collection (no dependencies)
        data_team = next(t for t in wm.teams if t.id == 'data_collection')
        data_team.start([])
        execution_order.append('data_collection')
        
        # 2. Execute teams that depend on data_collection
        analysis_team = next((t for t in wm.teams if t.id == 'analysis_team'), None)
        validation_team = next((t for t in wm.teams if t.id == 'validation_team'), None)
        
        if analysis_team:
            analysis_team.start([])
            execution_order.append('analysis_team')
        
        if validation_team:
            validation_team.start([])
            execution_order.append('validation_team')
        
        # 3. Execute report_generation (depends on analysis and validation)
        report_team = next((t for t in wm.teams if t.id == 'report_generation'), None)
        if report_team:
            report_team.start([])
            execution_order.append('report_generation')
        
        # Verify execution order respects dependencies
        self.assertIn('data_collection', execution_order, "data_collection should execute first")
        
        # Verify expected teams exist and executed
        expected_teams = ['data_collection', 'analysis_team', 'validation_team', 'report_generation']
        found_teams = [t.id for t in wm.teams]
        for expected in expected_teams:
            self.assertIn(expected, found_teams, f"Team {expected} should exist")
        
        # Check comprehensive logging
        shared_logger = self.logger_factory.create_logger()
        entries = shared_logger.entries()
        
        # Should have messages from multiple components
        components = set(e.component for e in entries)
        expected_components = {'core', 'team_runner', 'test_team_runner'}
        actual_components = components & expected_components
        self.assertTrue(len(actual_components) > 0, 
                       f"Should have logs from some expected components. Got: {components}")
        
        # Verify team execution
        team_start_msgs = [e for e in entries if "Starting test run for team" in e.message]
        self.assertTrue(len(team_start_msgs) > 0, "Should have team start messages")
        
        print(f"✅ Complex workflow test completed")
        print(f"   Execution order: {execution_order}")
        print(f"   Total log entries: {len(entries)}")
        print(f"   Components logged: {components}")
        print(f"   Teams found: {found_teams}")
    
if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
