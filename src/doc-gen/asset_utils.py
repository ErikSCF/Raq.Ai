#!/usr/bin/env python3
"""
Asset Utilities

Utility functions for workflow loading and team normalization, 
useful for testing and other workflow operations.
"""

import yaml
import os
from typing import List, Dict, Any

# Import TeamConfig for creating team configurations
from team import TeamConfig


class AssetUtils:
    """Utility class for workflow operations"""
    
    @staticmethod
    def load_workflow(workflow_file_path: str) -> List[TeamConfig]:
        """Load and parse workflow YAML, normalize teams with workflow defaults, return TeamConfig objects"""
        if not os.path.exists(workflow_file_path):
            raise FileNotFoundError(f"Workflow file not found: {workflow_file_path}")
        
        with open(workflow_file_path, 'r') as file:
            data = yaml.safe_load(file)
        
        if 'workflow' not in data:
            raise ValueError("Invalid workflow file: missing 'workflow' section")
        
        workflow_config = data['workflow']
        
        if 'teams' not in workflow_config:
            raise ValueError("Invalid workflow file: missing 'teams' section")
        
        # Normalize each team with workflow-level defaults and create TeamConfig objects
        team_configs = []
        for team_data in workflow_config['teams']:
            # Start with team data
            normalized_team = team_data.copy()
            
            # Add workflow-level defaults only if the property doesn't exist in the team
            normalized_team.setdefault('model', workflow_config.get('model'))
            normalized_team.setdefault('temperature', workflow_config.get('temperature'))
            normalized_team.setdefault('max_messages', workflow_config.get('max_messages'))
            normalized_team.setdefault('allow_repeated_speaker', workflow_config.get('allow_repeated_speaker'))
            normalized_team.setdefault('max_selector_attempts', workflow_config.get('max_selector_attempts'))
            normalized_team.setdefault('termination_keyword', workflow_config.get('termination_keyword'))
            
            # Set defaults for required fields
            normalized_team.setdefault('input_files', [])
            normalized_team.setdefault('step_files', [])
            normalized_team.setdefault('agent_result', None)
            normalized_team.setdefault('depends_on', None)
            
            # Validate required fields
            if 'id' not in normalized_team:
                raise ValueError("Team configuration missing required 'id' field")
            if 'template' not in normalized_team:
                raise ValueError(f"Team '{normalized_team.get('id', 'unknown')}' missing required 'template' field")
            if 'output_file' not in normalized_team:
                raise ValueError(f"Team '{normalized_team.get('id', 'unknown')}' missing required 'output_file' field")
            
            # Create TeamConfig object
            team_config = TeamConfig(
                id=normalized_team['id'],
                template=normalized_team['template'],
                output_file=normalized_team['output_file'],
                depends_on=normalized_team['depends_on'],
                input_files=normalized_team['input_files'],
                step_files=normalized_team['step_files'],
                agent_result=normalized_team['agent_result'],
                model=normalized_team.get('model'),
                temperature=normalized_team.get('temperature'),
                max_messages=normalized_team.get('max_messages'),
                allow_repeated_speaker=normalized_team.get('allow_repeated_speaker'),
                max_selector_attempts=normalized_team.get('max_selector_attempts'),
                termination_keyword=normalized_team.get('termination_keyword')
            )
            
            team_configs.append(team_config)
        
        return team_configs
    
    @staticmethod
    def load_workflow_from_dict(workflow_data: Dict[str, Any]) -> List[TeamConfig]:
        """Load workflow from a dictionary (useful for testing with in-memory data)"""
        if 'workflow' not in workflow_data:
            raise ValueError("Invalid workflow data: missing 'workflow' section")
        
        workflow_config = workflow_data['workflow']
        
        if 'teams' not in workflow_config:
            raise ValueError("Invalid workflow data: missing 'teams' section")
        
        # Normalize each team with workflow-level defaults and create TeamConfig objects
        team_configs = []
        for team_data in workflow_config['teams']:
            # Start with team data
            normalized_team = team_data.copy()
            
            # Add workflow-level defaults only if the property doesn't exist in the team
            normalized_team.setdefault('model', workflow_config.get('model'))
            normalized_team.setdefault('temperature', workflow_config.get('temperature'))
            normalized_team.setdefault('max_messages', workflow_config.get('max_messages'))
            normalized_team.setdefault('allow_repeated_speaker', workflow_config.get('allow_repeated_speaker'))
            normalized_team.setdefault('max_selector_attempts', workflow_config.get('max_selector_attempts'))
            normalized_team.setdefault('termination_keyword', workflow_config.get('termination_keyword'))
            
            # Set defaults for required fields
            normalized_team.setdefault('input_files', [])
            normalized_team.setdefault('step_files', [])
            normalized_team.setdefault('agent_result', None)
            normalized_team.setdefault('depends_on', None)
            
            # Validate required fields
            if 'id' not in normalized_team:
                raise ValueError("Team configuration missing required 'id' field")
            if 'template' not in normalized_team:
                raise ValueError(f"Team '{normalized_team.get('id', 'unknown')}' missing required 'template' field")
            if 'output_file' not in normalized_team:
                raise ValueError(f"Team '{normalized_team.get('id', 'unknown')}' missing required 'output_file' field")
            
            # Create TeamConfig object
            team_config = TeamConfig(
                id=normalized_team['id'],
                template=normalized_team['template'],
                output_file=normalized_team['output_file'],
                depends_on=normalized_team['depends_on'],
                input_files=normalized_team['input_files'],
                step_files=normalized_team['step_files'],
                agent_result=normalized_team['agent_result'],
                model=normalized_team.get('model'),
                temperature=normalized_team.get('temperature'),
                max_messages=normalized_team.get('max_messages'),
                allow_repeated_speaker=normalized_team.get('allow_repeated_speaker'),
                max_selector_attempts=normalized_team.get('max_selector_attempts'),
                termination_keyword=normalized_team.get('termination_keyword')
            )
            
            team_configs.append(team_config)
        
        return team_configs
