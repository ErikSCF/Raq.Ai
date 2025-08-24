#!/usr/bin/env python3
"""
Workflow Manager

Loads workflow configuration and creates teams with complete configuration
(workflow defaults + team-specific overrides).
"""

import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any, Generator

from team import Team
from workflow_orchestrator import WorkflowOrchestrator, TaskStatus
from asset_utils import AssetUtils
from logger import LoggerFactory, get_default_factory, Logger

from team_runner import TeamRunnerFactory
# AssetManager is required for workflows that provide assets; importing it
# directly ensures a missing module raises ImportError at runtime instead of
# silently falling back.
from asset_manager import AssetManager


class WorkflowManager:
    """Manages workflow configuration and team creation"""
    
    def __init__(self, workflow_file_path: str, logger_factory: Optional[LoggerFactory] = None):
        """Initialize with path to workflow.yaml file and optional logger factory"""
        self.workflow_file_path = workflow_file_path
        self.orchestrator = None
        self.teams = []
        self.logger_factory = logger_factory or get_default_factory()
        self.logger = self.logger_factory.create_logger("workflow")

    def run(self, timeout_seconds: Optional[int] = None):
        """Run the workflow manager with monitoring for completion/failure conditions
        
        Args:
            timeout_seconds: Maximum time to wait for workflow completion (None = no timeout)
        """
        import time
        
        self.logger.log("Running workflow manager...")
        # Queue all teams first
        for team in self.teams:
            team.run()

        # Now enable orchestration and trigger the first orchestration cycle
        if not self.orchestrator:
            self.logger.error("Orchestrator not initialized - call initialize() first")
            return False
            
        self.orchestrator.run()
        self.logger.log("Orchestration enabled - workflow execution started")
        
        # Governor/Message pump - monitor workflow progress
        import time
        for _ in self._monitor_workflow_execution(timeout_seconds):
            time.sleep(0.1)  # Brief sleep to prevent busy waiting
        
        # Check final status after monitoring completes
        if self.orchestrator.has_errors():
            return False
        elif self.orchestrator.is_complete():
            return True
        else:
            return False  # Timeout case
    
    def _monitor_workflow_execution(self, timeout_seconds: Optional[int] = None) -> Generator[None, None, None]:
        """Monitor workflow execution until completion, failure, or timeout
        
        Yields control back to caller on each iteration for cooperative multitasking.
        """
        import time
        
        start_time = time.time()
        self.logger.log(f"Monitoring workflow execution for {len(self.teams)} teams...")
        
        while True:
            current_time = time.time()
            
            # Check timeout
            if timeout_seconds and (current_time - start_time) > timeout_seconds:
                self.logger.error(f"Workflow timeout after {timeout_seconds} seconds")
                return
            
            # Check for failure condition
            if self.orchestrator.has_errors():
                self.logger.error("Workflow failed - stopping all teams")
                for team in self.teams:
                    try:
                        team.stop(force=True)
                    except Exception as e:
                        self.logger.error(f"Error stopping team {team.id}: {e}")
                return
            
            # Check for completion condition
            if self.orchestrator.is_complete():
                elapsed = current_time - start_time
                self.logger.log(f"Workflow completed successfully in {elapsed:.2f} seconds")
                return
            
            # Yield control back to caller (cooperative multitasking)
            yield


    def initialize(self, job_id: str,
                   document_type: str,
                   output_base_path: str,
                   orchestrator: WorkflowOrchestrator,
                   team_runner_factory: TeamRunnerFactory,
                   assets: List[str]):
        """Initialize workflow with observable store, create job output path and
        prepare assets/vector memory.

        All parameters are required to ensure proper workflow context setup.
        """
        self.orchestrator = orchestrator

        # Create the output folder and prepare the asset vector memory
        try:
            job_base = Path(output_base_path)
            # Create document-type specific folder and job folder
            job_folder = job_base / document_type / job_id
            job_folder.mkdir(parents=True, exist_ok=True)
            self.logger.log(f"Created job output folder: {job_folder}")

            # Create vector memory with provided assets (AssetManager import is required)
            try:
                manager = AssetManager(job_id, str(job_folder), assets)
                # create_vector_memory is async in the old manager; run it
                memory = None
                try:
                    memory = asyncio.run(manager.create_vector_memory())
                except RuntimeError:
                    # If we're already in an event loop, schedule and wait
                    loop = asyncio.get_event_loop()
                    memory = loop.run_until_complete(manager.create_vector_memory())
                self.asset_manager = manager
                self.memory = memory
                if memory:
                    self.logger.log(f"Asset memory configured for job {job_id}")
                else:
                    self.logger.log(f"Asset memory not configured for job {job_id}")
            except Exception as e:
                self.logger.error(f"Error preparing assets/vector memory: {e}")

        except Exception as e:
            self.logger.error(f"Error creating job folder: {e}")

        # Initialize all teams with the observable store
        team_configs = AssetUtils.load_workflow(self.workflow_file_path)
        
        # Create and initialize teams
        for team_config in team_configs:
            team = Team(team_config, self.logger_factory)
            team.initialize(self.orchestrator, team_runner_factory)
            self.teams.append(team)

        self.logger.log(f"Workflow initialized with {len(self.teams)} teams")
        return self.orchestrator


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        workflow_path = sys.argv[1]
    else:
        workflow_path = "documents/RAQ/workflow.yaml"
    
    try:
        wm = WorkflowManager(workflow_path)
        team_configs = AssetUtils.load_workflow(workflow_path)
        wm.logger.log("Workflow loaded successfully!")
        wm.logger.log(f"Teams: {[team_config.id for team_config in team_configs]}")
        
        # Initialize workflow with orchestrator
        wm.logger.log("Initializing workflow...")
        orchestrator = WorkflowOrchestrator()
        wm.initialize(
            job_id="example_job_001",
            document_type="RAQ", 
            output_base_path="./output",
            orchestrator=orchestrator,
            team_runner_factory=TeamRunnerFactory(wm.logger_factory),
            assets=["example_asset.pdf"]
        )
        
        # Test the orchestrator
        wm.logger.log("Testing orchestrator...")
        orchestrator.set('epic_discovery_001', TaskStatus.STARTED)
        orchestrator.set('epic_discovery_001', TaskStatus.COMPLETE)
            
    except Exception as e:
        print(f"Error: {e}")  # Keep one print for critical startup errors
