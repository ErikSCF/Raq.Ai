#!/usr/bin/env python3
"""
Workflow Manager

Loads workflow configuration and creates teams with complete configuration
(workflow defaults + team-specific overrides).
"""

import yaml
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional

from team import Team, TeamConfig
from observable import ObservableStore
from asset_utils import AssetUtils

# AssetManager is required for workflows that provide assets; importing it
# directly ensures a missing module raises ImportError at runtime instead of
# silently falling back.
from asset_manager import AssetManager


class WorkflowManager:
    """Manages workflow configuration and team creation"""
    
    def __init__(self, workflow_file_path: str):
        """Initialize with path to workflow.yaml file"""
        self.workflow_file_path = workflow_file_path
        self.observable = None

    
    def initialize(self, job_id: str,
                   document_type: str,
                   output_base_path: str,
                   observable: ObservableStore,
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
            print(f"Created job output folder: {job_folder}")

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
                    print(f"Asset memory configured for job {job_id}")
                else:
                    print(f"Asset memory not configured for job {job_id}")
            except Exception as e:
                print(f"Error preparing assets/vector memory: {e}")

        except Exception as e:
            print(f"Error creating job folder: {e}")

        # Initialize all teams with the observable store
        normalized_teams = AssetUtils.load_workflow(self.workflow_file_path)
        
        # Create and initialize teams
        team_count = 0
        for team_data in normalized_teams:
            # Create TeamConfig and Team
            team_config = TeamConfig(
                id=team_data['id'],
                template=team_data['template'],
                output_file=team_data['output_file'],
                depends_on=team_data['depends_on'],
                input_files=team_data['input_files'],
                step_files=team_data['step_files'],
                agent_result=team_data['agent_result'],
                model=team_data.get('model'),
                temperature=team_data.get('temperature'),
                max_messages=team_data.get('max_messages'),
                allow_repeated_speaker=team_data.get('allow_repeated_speaker'),
                max_selector_attempts=team_data.get('max_selector_attempts'),
                termination_keyword=team_data.get('termination_keyword')
            )
            team = Team(team_config)
            team.initialize(self.observable)
            team_count += 1

        print(f"Workflow initialized with {team_count} teams")
        return self.observable
