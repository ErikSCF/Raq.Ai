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
    
    def __init__(self, logger_factory: Optional[LoggerFactory] = None):
        """Initialize workflow manager with optional logger factory"""
        self.job_id = None
        self.document_type = None
        self.job_folder = None
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
        """Initialize workflow with orchestrator, create job output path and
        prepare assets/vector memory.

        The workflow configuration is copied from documents/{document_type}/ to the job folder
        and then loaded from there, making each job self-contained.
        """
        self.orchestrator = orchestrator
        self.job_id = job_id
        self.document_type = document_type
        
        # Create the job folder structure
        job_base = Path(output_base_path)
        self.job_folder = job_base / document_type / job_id
        self.job_folder.mkdir(parents=True, exist_ok=True)
        self.logger.log(f"Created job output folder: {self.job_folder}")
        
        # Copy all document template files to job folder
        self._copy_document_template_files()
        
        # Now use the copied workflow.yaml from the job folder
        workflow_file_path = str(self.job_folder / "workflow.yaml")
        
        if not Path(workflow_file_path).exists():
            raise FileNotFoundError(f"Workflow configuration not found after copy: {workflow_file_path}")
        
        self.logger.log(f"Using workflow configuration: {workflow_file_path}")

        # Create vector memory with provided assets (AssetManager import is required)
        try:
            manager = AssetManager(job_id, str(self.job_folder), document_type, assets)
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

        # Initialize all teams with the orchestrator using the copied workflow config
        team_configs = AssetUtils.load_workflow(workflow_file_path)
        
        # Create and initialize teams
        for team_config in team_configs:
            # Set runtime context
            team_config.job_folder = str(self.job_folder)
            team_config.document_type = self.document_type
            
            team = Team(team_config, self.logger_factory)
            team.initialize(self.orchestrator, team_runner_factory, memory)
            self.teams.append(team)

        self.logger.log(f"Workflow initialized with {len(self.teams)} teams")
        return self.orchestrator
    
    def _copy_document_template_files(self):
        """Copy all document template files from documents/{document_type}/ to job folder"""
        import shutil
        
        # Check if we're in a test environment by looking for tests/documents first
        current_file = Path(__file__)
        test_source_dir = current_file.parent / "tests" / "documents" / self.document_type
        prod_source_dir = current_file.parent / "documents" / self.document_type
        
        if test_source_dir.exists():
            source_dir = test_source_dir
        elif prod_source_dir.exists():
            source_dir = prod_source_dir
        else:
            raise FileNotFoundError(f"Document type '{self.document_type}' not found in documents/ or tests/documents/")
        
        self.logger.log(f"Copying document template files from {source_dir}")
        
        # Copy all files from the document type folder
        for item in source_dir.iterdir():
            if item.is_file():
                destination = self.job_folder / item.name
                shutil.copy2(item, destination)
                self.logger.log(f"Copied template file: {item.name}")
            elif item.is_dir():
                # Copy subdirectories recursively
                destination = self.job_folder / item.name
                shutil.copytree(item, destination, exist_ok=True)
                self.logger.log(f"Copied template directory: {item.name}")
        
        self.logger.log(f"Document template files copied to job folder")


if __name__ == "__main__":
    # Example usage
    import sys
    
    try:
        wm = WorkflowManager()
        
        # Initialize workflow with orchestrator
        print("Initializing workflow...")
        orchestrator = WorkflowOrchestrator()
        from team_runner import TeamRunnerFactory
        
        wm.initialize(
            job_id="example_job_001",
            document_type="RAQ", 
            output_base_path="./output",
            orchestrator=orchestrator,
            team_runner_factory=TeamRunnerFactory(wm.logger_factory),
            assets=["example_asset.pdf"] if len(sys.argv) > 1 else []
        )
        
        print("Workflow initialized successfully!")
        print(f"Teams: {[team.id for team in wm.teams]}")
        
        # Test the orchestrator
        print("Testing orchestrator...")
        orchestrator.set('team_001', TaskStatus.STARTED)
        orchestrator.set('team_001', TaskStatus.COMPLETE)
            
    except Exception as e:
        print(f"Error: {e}")  # Keep one print for critical startup errors
