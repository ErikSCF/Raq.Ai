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

# Optional asset manager used to populate vector DB for RAG-enabled teams.
try:
    from asset_manager import AssetManager
except Exception:
    AssetManager = None


class WorkflowManager:
    """Manages workflow configuration and team creation"""
    
    def __init__(self, workflow_file_path: str):
        """Initialize with path to workflow.yaml file"""
        self.workflow_file_path = workflow_file_path
        self.workflow_config = None
        self.teams = []
        self.observable = None
        self._load_workflow()
    
    def initialize(self, observable: ObservableStore = None,
                   job_id: Optional[str] = None,
                   document_type: Optional[str] = None,
                   output_base_path: Optional[str] = None,
                   assets: Optional[List[str]] = None):
        """Initialize workflow with observable store, create job output path and
        optionally prepare assets/vector memory.

        Backwards-compatible: if called with only `observable`, behaves like before.
        """
        if observable is None:
            observable = ObservableStore()

        self.observable = observable

        # If job/output parameters are provided, create the output folder and
        # optionally build the asset vector memory.
        if job_id and document_type and output_base_path:
            try:
                job_base = Path(output_base_path)
                # Create document-type specific folder and job folder
                job_folder = job_base / document_type / job_id
                job_folder.mkdir(parents=True, exist_ok=True)
                print(f"Created job output folder: {job_folder}")

                # If AssetManager is available and assets were provided, create vector memory
                if assets and AssetManager is not None:
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
        for team in self.teams:
            team.initialize(self.observable)

        print(f"Workflow '{self.get_workflow_info()['name']}' initialized with {len(self.teams)} teams")
        return self.observable
    
    def _load_workflow(self):
        """Load and parse the workflow configuration file"""
        if not os.path.exists(self.workflow_file_path):
            raise FileNotFoundError(f"Workflow file not found: {self.workflow_file_path}")
        
        with open(self.workflow_file_path, 'r') as file:
            data = yaml.safe_load(file)
        
        if 'workflow' not in data:
            raise ValueError("Invalid workflow file: missing 'workflow' section")
        
        self.workflow_config = data['workflow']
        self._create_team_configs()
    
    def _create_team_configs(self):
        """Create complete team configurations with defaults + overrides"""
        workflow_defaults = self._extract_workflow_defaults()

        if 'teams' not in self.workflow_config:
            raise ValueError("Invalid workflow file: missing 'teams' section")
        
        self.teams = []
        for team_data in self.workflow_config['teams']:
            team_config = self._create_team_config(team_data, workflow_defaults)
            team = Team(team_config)
            self.teams.append(team)
    
    def _extract_workflow_defaults(self) -> Dict[str, Any]:
        """Extract default configuration values from workflow"""
        defaults = {}
        
        # Extract AutoGen configuration defaults
        autogen_keys = [
            'model', 'temperature', 'max_messages', 
            'allow_repeated_speaker', 'max_selector_attempts', 'termination_keyword'
        ]
        
        for key in autogen_keys:
            if key in self.workflow_config:
                defaults[key] = self.workflow_config[key]
        
        return defaults
    
    def _create_team_config(self, team_data: Dict[str, Any], defaults: Dict[str, Any]) -> TeamConfig:
        """Create a complete team configuration by merging defaults with team-specific overrides"""
        
        # Start with defaults
        config = defaults.copy()
        
        # Override with team-specific values
        for key, value in team_data.items():
            config[key] = value
        
        # Ensure required fields have defaults
        config.setdefault('input_files', [])
        config.setdefault('step_files', [])
        config.setdefault('agent_result', None)
        config.setdefault('depends_on', None)
        
        # Validate required fields
        if 'id' not in config:
            raise ValueError("Team configuration missing required 'id' field")
        if 'template' not in config:
            raise ValueError(f"Team '{config.get('id', 'unknown')}' missing required 'template' field")
        if 'output_file' not in config:
            raise ValueError(f"Team '{config.get('id', 'unknown')}' missing required 'output_file' field")
        
        return TeamConfig(
            id=config['id'],
            template=config['template'],
            output_file=config['output_file'],
            depends_on=config['depends_on'],
            input_files=config['input_files'],
            step_files=config['step_files'],
            agent_result=config['agent_result'],
            model=config['model'],
            temperature=config['temperature'],
            max_messages=config['max_messages'],
            allow_repeated_speaker=config['allow_repeated_speaker'],
            max_selector_attempts=config['max_selector_attempts'],
            termination_keyword=config['termination_keyword']
        )
    
    def get_teams(self) -> List[Team]:
        """Get all team configurations"""
        return self.teams.copy()
    
    def get_team_config(self, team_id: str) -> Team:
        """Get configuration for a specific team"""
        for team in self.teams:
            if team.id == team_id:
                return team
        raise ValueError(f"Team not found: {team_id}")
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """Get general workflow information"""
        return {
            'name': self.workflow_config.get('name', 'Unnamed Workflow'),
            'description': self.workflow_config.get('description', ''),
            'total_teams': len(self.teams)
        }
    
    def get_dependency_order(self) -> List[List[str]]:
        """Get teams ordered by dependencies (for parallel execution planning)"""
        # Build dependency graph
        team_deps = {}
        for team in self.teams:
            team_deps[team.id] = team.depends_on
        
        # Topological sort to get execution order
        levels = []
        remaining_teams = set(team.id for team in self.teams)
        
        while remaining_teams:
            # Find teams with no remaining dependencies
            ready_teams = []
            for team_id in remaining_teams:
                dep = team_deps[team_id]
                if dep is None or dep not in remaining_teams:
                    ready_teams.append(team_id)
            
            if not ready_teams:
                raise ValueError("Circular dependency detected in workflow")
            
            levels.append(ready_teams)
            remaining_teams -= set(ready_teams)
        
        return levels
    
    def validate_workflow(self) -> List[str]:
        """Validate the workflow configuration and return any issues"""
        issues = []
        
        # Check for circular dependencies
        try:
            self.get_dependency_order()
        except ValueError as e:
            issues.append(str(e))
        
        # Check for missing dependencies
        team_ids = {team.id for team in self.teams}
        for team in self.teams:
            if team.depends_on and team.depends_on not in team_ids:
                issues.append(f"Team '{team.id}' depends on unknown team '{team.depends_on}'")
        
        # Check for duplicate team ids
        ids = [team.id for team in self.teams]
        duplicates = set([team_id for team_id in ids if ids.count(team_id) > 1])
        for duplicate in duplicates:
            issues.append(f"Duplicate team id: '{duplicate}'")
        
        return issues


# Convenience function for easy usage
def load_workflow(workflow_file_path: str) -> WorkflowManager:
    """Load a workflow from a YAML file"""
    return WorkflowManager(workflow_file_path)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        workflow_path = sys.argv[1]
    else:
        workflow_path = "documents/RAQ/workflow.yaml"
    
    try:
        wm = load_workflow(workflow_path)
        print("Workflow loaded successfully!")
        print(f"Workflow: {wm.get_workflow_info()}")
        print(f"Teams: {[team.id for team in wm.get_teams()]}")
        print(f"Execution order: {wm.get_dependency_order()}")
        
        # Validate
        issues = wm.validate_workflow()
        if issues:
            print("Validation issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✅ Workflow validation passed!")
        
        # Initialize workflow with observable store
        print("\nInitializing workflow...")
        observable = wm.initialize()
        
        # Test the observable store
        print("\nTesting observable store...")
        observable.set('team_status', {'epic_discovery_001': 'running'})
        observable.set('team_status', {'epic_discovery_001': 'completed', 'document_assembly_001': 'running'})
            
    except Exception as e:
        print(f"Error: {e}")
