#!/usr/bin/env python3
"""
Workflow Manager for Document Generation Pipeline

This module handles workflow configuration loading, dependency analysis, 
and parallel execution planning.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
import asyncio


class WorkflowManager:
    """Manages workflow configuration and execution dependencies."""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.documents_dir = self.base_dir / "documents"
        self.workflow_config = None
        self.document_type_dir = None
    
    def set_document_type(self, document_type: str):
        """Set the document type and load the workflow configuration."""
        self.document_type_dir = self.documents_dir / document_type
        if not self.document_type_dir.exists():
            raise ValueError(f"Document type '{document_type}' not found in {self.documents_dir}")
        
        # Load workflow configuration
        workflow_file = self.document_type_dir / "workflow.yaml"
        if not workflow_file.exists():
            raise FileNotFoundError(f"Workflow configuration not found: {workflow_file}")
        
        self.workflow_config = self.load_yaml_file(workflow_file)
        
        # Verify all team YAML files exist
        missing_teams = []
        for team in self.workflow_config['workflow']['teams']:
            team_file = self.document_type_dir / f"{team['name']}.yaml"
            if not team_file.exists():
                missing_teams.append(str(team_file))
        
        if missing_teams:
            raise FileNotFoundError(f"Team configuration files not found: {missing_teams}")
        
        print(f"✓ Loaded workflow: {self.workflow_config['workflow']['name']}")
        print(f"✓ Teams: {[team['name'] for team in self.workflow_config['workflow']['teams']]}")
    
    def get_team_config(self, team_name: str) -> Dict[str, Any]:
        """
        Get complete team configuration by loading team YAML and merging with workflow overrides.
        """
        # Load the team YAML file first to get the full structure
        team_yaml_path = self.base_dir / "documents" / self.document_type_dir / f"{team_name}.yaml"
        if not team_yaml_path.exists():
            raise FileNotFoundError(f"Team YAML file not found: {team_yaml_path}")
        
        # Load the full team structure
        team_config = self.load_yaml_file(team_yaml_path)
        
        # Get workflow configuration overrides
        if self.workflow_config:
            workflow = self.workflow_config['workflow']
            
            # Apply workflow defaults
            workflow_defaults = {
                'model': workflow.get('model', 'gpt-4o-mini'),
                'temperature': workflow.get('temperature', 0.3),
                'max_messages': workflow.get('max_messages', 50),
                'allow_repeated_speaker': workflow.get('allow_repeated_speaker', True),
                'max_selector_attempts': workflow.get('max_selector_attempts', 3),
                'termination_keyword': workflow.get('termination_keyword', 'TERMINATE')
            }
            
            # Apply workflow defaults to team config
            for key, value in workflow_defaults.items():
                if key not in team_config:
                    team_config[key] = value
            
            # Find team-specific overrides in workflow teams section
            for team in workflow.get('teams', []):
                if team.get('name') == team_name:
                    # Apply team-specific overrides
                    for key, value in team.items():
                        if key != 'name':  # Don't override the name
                            team_config[key] = value
                    break
        
        return team_config

    def load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML file and return parsed data."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get_root_teams(self) -> List[Dict[str, Any]]:
        """Get teams that have no dependencies (root nodes)."""
        if not self.workflow_config:
            return []
        
        root_teams = []
        for team in self.workflow_config['workflow']['teams']:
            depends_on = team.get('depends_on')
            if depends_on is None:
                root_teams.append(team)
        
        return root_teams
    
    def get_dependent_teams(self, completed_team: str) -> List[Dict[str, Any]]:
        """Get teams that depend on the completed team (can now be executed)."""
        if not self.workflow_config:
            return []
        
        dependent_teams = []
        for team in self.workflow_config['workflow']['teams']:
            depends_on = team.get('depends_on')
            if depends_on == completed_team:
                dependent_teams.append(team)
        
        return dependent_teams
    
    def build_dependency_tree(self) -> Dict[str, Any]:
        """
        Build a nested dependency tree structure.
        Returns a tree where each team contains its dependent teams.
        """
        if not self.workflow_config:
            return {}
        
        teams = self.workflow_config['workflow']['teams']
        
        # Create a map of team instances by name for easy lookup
        teams_by_name = {}
        for i, team in enumerate(teams):
            team_key = f"{team['name']}_{i}"  # Unique key for this instance
            teams_by_name[team_key] = {
                **team,
                'index': i,
                'key': team_key,
                'dependents': []
            }
        
        # Build dependency relationships
        for team_key, team_data in teams_by_name.items():
            depends_on = team_data.get('depends_on')
            if depends_on:
                # Find the dependency - could be multiple teams with same name
                for dep_key, dep_data in teams_by_name.items():
                    if dep_data['name'] == depends_on:
                        # Add this team as a dependent of the dependency
                        dep_data['dependents'].append(team_data)
        
        return teams_by_name
    
    def get_execution_phases(self, dependency_tree: Dict[str, Any], last_team_executed: str = None) -> List[List[Dict[str, Any]]]:
        """
        Get execution phases from dependency tree.
        Each phase contains teams that can run in parallel.
        """
        phases = []
        completed_teams = set()
        
        # If resuming, mark the last executed team as completed
        if last_team_executed:
            for team_key, team_data in dependency_tree.items():
                if team_data['name'] == last_team_executed:
                    completed_teams.add(team_key)
                    break
        
        # Continue until all teams are processed
        while len(completed_teams) < len(dependency_tree):
            ready_teams = []
            
            for team_key, team_data in dependency_tree.items():
                if team_key in completed_teams:
                    continue
                
                # Check if this team's dependencies are satisfied
                depends_on = team_data.get('depends_on')
                if depends_on is None:
                    # Root team - always ready
                    ready_teams.append(team_data)
                else:
                    # Handle both single dependency (string) and multiple dependencies (list)
                    dependencies = depends_on if isinstance(depends_on, list) else [depends_on]
                    
                    # Check if all dependencies are completed
                    all_deps_completed = True
                    for dep_name in dependencies:
                        dep_completed = False
                        for completed_key in completed_teams:
                            completed_team = dependency_tree[completed_key]
                            if completed_team['name'] == dep_name:
                                dep_completed = True
                                break
                        if not dep_completed:
                            all_deps_completed = False
                            break
                    
                    if all_deps_completed:
                        ready_teams.append(team_data)
            
            if not ready_teams:
                # No more teams can be executed
                remaining = [k for k in dependency_tree.keys() if k not in completed_teams]
                if remaining:
                    raise ValueError(f"Circular dependency or unresolved dependencies for: {remaining}")
                break
            
            phases.append(ready_teams)
            
            # Mark these teams as completed
            for team in ready_teams:
                completed_teams.add(team['key'])
        
        return phases
    
    def can_execute_team(self, team_name: str, completed_teams: Set[str]) -> bool:
        """Check if a team can be executed given completed teams."""
        # Find the team
        target_team = None
        for team in self.workflow_config['workflow']['teams']:
            if team['name'] == team_name:
                target_team = team
                break
        
        if not target_team:
            return False
        
        depends_on = target_team.get('depends_on')
        if depends_on is None:
            # Root team - can always execute
            return True
        
        # Check if dependency is completed
        return depends_on in completed_teams
    
    def get_ready_teams(self, completed_teams: Set[str]) -> List[Dict[str, Any]]:
        """Get all teams that are ready to execute (dependencies satisfied)."""
        if not self.workflow_config:
            return []
        
        ready_teams = []
        for team in self.workflow_config['workflow']['teams']:
            team_name = team['name']
            if team_name not in completed_teams and self.can_execute_team(team_name, completed_teams):
                ready_teams.append(team)
        
        return ready_teams
    
    def filter_teams_from_last_executed(self, last_team_executed: str) -> List[Dict[str, Any]]:
        """Filter teams to only include those that depend on the last executed team."""
        if not self.workflow_config:
            return []
        
        teams = self.workflow_config['workflow']['teams']
        team_names = [team['name'] for team in teams]
        
        # Validate that the last_team_executed exists
        if last_team_executed not in team_names:
            raise ValueError(f"Team '{last_team_executed}' not found in workflow. Available teams: {team_names}")
        
        # Build dependency graph: team_name -> [teams_that_depend_on_it]
        dependents_graph = {team_name: [] for team_name in team_names}
        
        for team in teams:
            team_name = team['name']
            depends_on = team.get('depends_on')
            
            if depends_on:
                dependents_graph[depends_on].append(team_name)
        
        # Find all teams that transitively depend on last_team_executed
        dependent_teams = set()
        queue = [last_team_executed]
        visited = set()
        
        while queue:
            current_team = queue.pop(0)
            if current_team in visited:
                continue
            visited.add(current_team)
            
            # Add direct dependents
            for dependent in dependents_graph[current_team]:
                if dependent not in dependent_teams:
                    dependent_teams.add(dependent)
                    queue.append(dependent)
        
        # Return teams in execution order (preserve workflow order)
        filtered_teams = []
        for team in teams:
            if team['name'] in dependent_teams:
                filtered_teams.append(team)
        
        return filtered_teams
    
    def get_execution_plan(self, last_team_executed: str = None) -> List[List[Dict[str, Any]]]:
        """
        Get execution plan as a list of execution phases using dependency tree.
        Each phase contains teams that can be executed in parallel.
        """
        if not self.workflow_config:
            return []
        
        # Build the dependency tree
        dependency_tree = self.build_dependency_tree()
        
        # Get execution phases from the tree
        phases = self.get_execution_phases(dependency_tree, last_team_executed)
        
        return phases
