#!/usr/bin/env python3
"""
Workflow Manager

Loads workflow configuration and creates teams with complete configuration
(workflow defaults + team-specific overrides).
"""

import asyncio
from pathlib import Path
from typing import List, Optional

from team import Team
from observable import ObservableStore
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
        self.observable = None
        self.teams = []
        self.logger_factory = logger_factory or get_default_factory()
        self.logger = self.logger_factory.create_logger("workflow")

    def run(self):
        """Run the workflow manager"""
        self.logger.log("Running workflow manager...")
        # Here you would add the logic to start the workflow
        # For example, you might trigger the first team's tasks
        # and monitor their progress via the observable store.

        for team in self.teams:
            team.run()


    def initialize(self, job_id: str,
                   document_type: str,
                   output_base_path: str,
                   observable: ObservableStore,
                   team_runner_factory: TeamRunnerFactory,
                   assets: List[str]):
        """Initialize workflow with observable store, create job output path and
        prepare assets/vector memory.

        All parameters are required to ensure proper workflow context setup.
        """
        self.observable = observable

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
            team.initialize(self.observable, team_runner_factory)
            self.teams.append(team)

        self.logger.log(f"Workflow initialized with {len(self.teams)} teams")
        return self.observable


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
        
        # Initialize workflow with observable store
        wm.logger.log("Initializing workflow...")
        observable = ObservableStore()
        wm.initialize(
            job_id="example_job_001",
            document_type="RAQ", 
            output_base_path="./output",
            observable=observable,
            team_runner_factory=TeamRunnerFactory(),
            assets=["example_asset.pdf"]
        )
        
        # Test the observable store
        wm.logger.log("Testing observable store...")
        observable.set('team_status', {'epic_discovery_001': 'running'})
        observable.set('team_status', {'epic_discovery_001': 'completed', 'document_assembly_001': 'running'})
            
    except Exception as e:
        print(f"Error: {e}")  # Keep one print for critical startup errors
