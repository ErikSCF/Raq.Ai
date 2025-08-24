#!/usr/bin/env python3
"""
Tests for Workflow Manager

Test-driven development for workflow configuration loading and management.
"""

import unittest
import tempfile
import os
import yaml
import sys
from unittest.mock import patch, mock_open

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow import WorkflowManager, load_workflow
from team import Team, TeamConfig


class TestWorkflowManager(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.sample_workflow = {
            'workflow': {
                'name': 'Test Workflow',
                'description': 'A test workflow',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {
                        'id': 'team1_001',
                        'template': 'Team1.yaml',
                        'output_file': 'output1.md',
                        'depends_on': None,
                        'input_files': ['input1.txt'],
                        'step_files': [],
                        'agent_result': None
                    },
                    {
                        'id': 'team2_001',
                        'template': 'Team2.yaml',
                        'output_file': 'output2.md',
                        'depends_on': 'team1_001',
                        'input_files': ['output1.md'],
                        'step_files': ['output1.steps.md'],
                        'agent_result': None,
                        'max_messages': 30  # Override default
                    }
                ]
            }
        }
    
    def create_temp_workflow_file(self, workflow_data):
        """Create a temporary workflow file for testing"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(workflow_data, temp_file, default_flow_style=False)
        temp_file.close()
        return temp_file.name
    
    def test_load_valid_workflow(self):
        """Test loading a valid workflow file"""
        temp_file = self.create_temp_workflow_file(self.sample_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            # Check workflow info
            info = wm.get_workflow_info()
            self.assertEqual(info['name'], 'Test Workflow')
            self.assertEqual(info['description'], 'A test workflow')
            self.assertEqual(info['total_teams'], 2)
            
            # Check teams
            teams = wm.get_teams()
            self.assertEqual(len(teams), 2)
            self.assertEqual(teams[0].id, 'team1_001')
            self.assertEqual(teams[1].id, 'team2_001')
            
        finally:
            os.unlink(temp_file)
    
    def test_team_config_merging(self):
        """Test that team configurations properly merge defaults with overrides"""
        temp_file = self.create_temp_workflow_file(self.sample_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            team1 = wm.get_team_config('team1_001')
            team2 = wm.get_team_config('team2_001')
            
            # Team1 should use defaults
            self.assertEqual(team1.model, 'gpt-4o-mini')
            self.assertEqual(team1.temperature, 0.3)
            self.assertEqual(team1.max_messages, 50)
            self.assertEqual(team1.allow_repeated_speaker, False)
            
            # Team2 should override max_messages but keep other defaults
            self.assertEqual(team2.model, 'gpt-4o-mini')
            self.assertEqual(team2.temperature, 0.3)
            self.assertEqual(team2.max_messages, 30)  # Overridden
            self.assertEqual(team2.allow_repeated_speaker, False)
            
        finally:
            os.unlink(temp_file)
    
    def test_get_specific_team_config(self):
        """Test getting configuration for a specific team"""
        temp_file = self.create_temp_workflow_file(self.sample_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            team1 = wm.get_team_config('team1_001')
            self.assertEqual(team1.id, 'team1_001')
            self.assertEqual(team1.template, 'Team1.yaml')
            self.assertEqual(team1.output_file, 'output1.md')
            self.assertEqual(team1.depends_on, None)
            self.assertEqual(team1.input_files, ['input1.txt'])
            
            team2 = wm.get_team_config('team2_001')
            self.assertEqual(team2.id, 'team2_001')
            self.assertEqual(team2.template, 'Team2.yaml')
            self.assertEqual(team2.depends_on, 'team1_001')
            
        finally:
            os.unlink(temp_file)
    
    def test_get_nonexistent_team_raises_error(self):
        """Test that getting a nonexistent team raises ValueError"""
        temp_file = self.create_temp_workflow_file(self.sample_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            with self.assertRaises(ValueError) as context:
                wm.get_team_config('nonexistent_team_001')
            
            self.assertIn('Team not found', str(context.exception))
            
        finally:
            os.unlink(temp_file)
    
    def test_dependency_order_simple(self):
        """Test dependency order calculation for simple case"""
        temp_file = self.create_temp_workflow_file(self.sample_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            order = wm.get_dependency_order()
            
            # Should have 2 levels: [team1_001], [team2_001]
            self.assertEqual(len(order), 2)
            self.assertEqual(order[0], ['team1_001'])
            self.assertEqual(order[1], ['team2_001'])
            
        finally:
            os.unlink(temp_file)
    
    def test_dependency_order_parallel(self):
        """Test dependency order with parallel teams"""
        parallel_workflow = {
            'workflow': {
                'name': 'Parallel Test',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {'id': 'root_001', 'template': 'Root.yaml', 'output_file': 'root.md', 'depends_on': None},
                    {'id': 'branch1_001', 'template': 'Branch1.yaml', 'output_file': 'branch1.md', 'depends_on': 'root_001'},
                    {'id': 'branch2_001', 'template': 'Branch2.yaml', 'output_file': 'branch2.md', 'depends_on': 'root_001'},
                    {'id': 'merge_001', 'template': 'Merge.yaml', 'output_file': 'merge.md', 'depends_on': 'branch1_001'}
                ]
            }
        }
        
        temp_file = self.create_temp_workflow_file(parallel_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            order = wm.get_dependency_order()
            
            # Should have 3 levels: [root_001], [branch1_001, branch2_001], [merge_001]
            self.assertEqual(len(order), 3)
            self.assertEqual(order[0], ['root_001'])
            self.assertIn('branch1_001', order[1])
            self.assertIn('branch2_001', order[1])
            self.assertEqual(len(order[1]), 2)  # Both branches in same level
            self.assertEqual(order[2], ['merge_001'])
            
        finally:
            os.unlink(temp_file)
    
    def test_validation_duplicate_names(self):
        """Test validation catches duplicate team names"""
        duplicate_workflow = {
            'workflow': {
                'name': 'Duplicate Test',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {'id': 'team1_001', 'template': 'Team1.yaml', 'output_file': 'output1.md', 'depends_on': None},
                    {'id': 'team1_001', 'template': 'Team1.yaml', 'output_file': 'output2.md', 'depends_on': None}
                ]
            }
        }
        
        temp_file = self.create_temp_workflow_file(duplicate_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            issues = wm.validate_workflow()
            
            self.assertTrue(any('Duplicate team id' in issue for issue in issues))
            
        finally:
            os.unlink(temp_file)
    
    def test_validation_missing_dependency(self):
        """Test validation catches missing dependencies"""
        missing_dep_workflow = {
            'workflow': {
                'name': 'Missing Dep Test',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {'id': 'team1_001', 'template': 'Team1.yaml', 'output_file': 'output1.md', 'depends_on': 'nonexistent_team_001'}
                ]
            }
        }
        
        temp_file = self.create_temp_workflow_file(missing_dep_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            issues = wm.validate_workflow()
            
            self.assertTrue(any('depends on unknown team' in issue for issue in issues))
            
        finally:
            os.unlink(temp_file)
    
    def test_validation_circular_dependency(self):
        """Test validation catches circular dependencies"""
        circular_workflow = {
            'workflow': {
                'name': 'Circular Test',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {'id': 'team1_001', 'template': 'Team1.yaml', 'output_file': 'output1.md', 'depends_on': 'team2_001'},
                    {'id': 'team2_001', 'template': 'Team2.yaml', 'output_file': 'output2.md', 'depends_on': 'team1_001'}
                ]
            }
        }
        
        temp_file = self.create_temp_workflow_file(circular_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            
            issues = wm.validate_workflow()
            
            self.assertTrue(any('Circular dependency' in issue for issue in issues))
            
        finally:
            os.unlink(temp_file)
    
    def test_missing_workflow_file(self):
        """Test that missing workflow file raises FileNotFoundError"""
        with self.assertRaises(FileNotFoundError):
            WorkflowManager('/nonexistent/path/workflow.yaml')
    
    def test_invalid_workflow_structure(self):
        """Test that invalid workflow structure raises ValueError"""
        invalid_workflow = {'not_workflow': 'invalid'}
        
        temp_file = self.create_temp_workflow_file(invalid_workflow)
        
        try:
            with self.assertRaises(ValueError) as context:
                WorkflowManager(temp_file)
            
            self.assertIn('missing \'workflow\' section', str(context.exception))
            
        finally:
            os.unlink(temp_file)
    
    def test_missing_teams_section(self):
        """Test that missing teams section raises ValueError"""
        no_teams_workflow = {
            'workflow': {
                'name': 'No Teams',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE'
                # Missing 'teams' section
            }
        }
        
        temp_file = self.create_temp_workflow_file(no_teams_workflow)
        
        try:
            with self.assertRaises(ValueError) as context:
                WorkflowManager(temp_file)
            
            self.assertIn('missing \'teams\' section', str(context.exception))
            
        finally:
            os.unlink(temp_file)
    
    def test_missing_required_team_fields(self):
        """Test that missing required team fields raises ValueError"""
        missing_name_workflow = {
            'workflow': {
                'name': 'Missing Name Test',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {'template': 'TestTeam.yaml', 'output_file': 'output.md'}  # Missing 'id'
                ]
            }
        }
        
        temp_file = self.create_temp_workflow_file(missing_name_workflow)
        
        try:
            with self.assertRaises(ValueError) as context:
                WorkflowManager(temp_file)
            
            self.assertIn('missing required \'id\' field', str(context.exception))
            
        finally:
            os.unlink(temp_file)
    
    def test_default_field_values(self):
        """Test that default values are set for optional fields"""
        minimal_workflow = {
            'workflow': {
                'name': 'Minimal Test',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {'id': 'minimal_team_001', 'template': 'MinimalTeam.yaml', 'output_file': 'output.md'}
                ]
            }
        }
        
        temp_file = self.create_temp_workflow_file(minimal_workflow)
        
        try:
            wm = WorkflowManager(temp_file)
            team = wm.get_team_config('minimal_team_001')
            
            # Check that defaults are set
            self.assertEqual(team.input_files, [])
            self.assertEqual(team.step_files, [])
            self.assertEqual(team.agent_result, None)
            self.assertEqual(team.depends_on, None)
            
        finally:
            os.unlink(temp_file)


class TestConvenienceFunction(unittest.TestCase):
    """Test the convenience load_workflow function"""
    
    def test_load_workflow_function(self):
        """Test the load_workflow convenience function"""
        sample_workflow = {
            'workflow': {
                'name': 'Convenience Test',
                'model': 'gpt-4o-mini',
                'temperature': 0.3,
                'max_messages': 50,
                'allow_repeated_speaker': False,
                'max_selector_attempts': 3,
                'termination_keyword': 'TERMINATE',
                'teams': [
                    {'id': 'test_team_001', 'template': 'TestTeam.yaml', 'output_file': 'test.md'}
                ]
            }
        }
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(sample_workflow, temp_file, default_flow_style=False)
        temp_file.close()
        
        try:
            wm = load_workflow(temp_file.name)
            
            self.assertIsInstance(wm, WorkflowManager)
            self.assertEqual(wm.get_workflow_info()['name'], 'Convenience Test')
            
        finally:
            os.unlink(temp_file.name)


class TestTeamConfig(unittest.TestCase):
    """Test the TeamConfig dataclass"""
    
    def test_team_config_creation(self):
        """Test creating a TeamConfig instance"""
        config = TeamConfig(
            id='test_team_001',
            template='TestTeam.yaml',
            output_file='test.md',
            depends_on='other_team_001',
            input_files=['input.txt'],
            step_files=['steps.md'],
            agent_result='result',
            model='gpt-4o-mini',
            temperature=0.5,
            max_messages=25,
            allow_repeated_speaker=True,
            max_selector_attempts=5,
            termination_keyword='STOP'
        )
        
        self.assertEqual(config.id, 'test_team_001')
        self.assertEqual(config.template, 'TestTeam.yaml')
        self.assertEqual(config.output_file, 'test.md')
        self.assertEqual(config.depends_on, 'other_team_001')
        self.assertEqual(config.input_files, ['input.txt'])
        self.assertEqual(config.step_files, ['steps.md'])
        self.assertEqual(config.agent_result, 'result')
        self.assertEqual(config.model, 'gpt-4o-mini')
        self.assertEqual(config.temperature, 0.5)
        self.assertEqual(config.max_messages, 25)
        self.assertEqual(config.allow_repeated_speaker, True)
        self.assertEqual(config.max_selector_attempts, 5)
        self.assertEqual(config.termination_keyword, 'STOP')


if __name__ == "__main__":
    unittest.main()
