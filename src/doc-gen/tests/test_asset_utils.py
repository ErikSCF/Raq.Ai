#!/usr/bin/env python3
"""
Tests for AssetUtils class

Test workflow loading and team normalization functionality.
"""

import unittest
import tempfile
import os
import yaml
from pathlib import Path

# Add parent directory to path to import modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from asset_utils import AssetUtils
from team import TeamConfig


class TestAssetUtils(unittest.TestCase):
    """Test cases for AssetUtils class"""
    
    def setUp(self):
        """Set up test fixtures"""
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
                        'id': 'team1',
                        'template': 'template1.yaml',
                        'output_file': 'output1.md'
                    },
                    {
                        'id': 'team2', 
                        'template': 'template2.yaml',
                        'output_file': 'output2.md',
                        'model': 'gpt-4',  # Override workflow default
                        'temperature': 0.7,  # Override workflow default
                        'input_files': ['custom_input.md']  # Custom value
                    }
                ]
            }
        }
    
    def test_load_workflow_from_dict(self):
        """Test loading workflow from dictionary"""
        team_configs = AssetUtils.load_workflow_from_dict(self.test_workflow_data)
        
        # Should return 2 TeamConfig objects
        self.assertEqual(len(team_configs), 2)
        self.assertIsInstance(team_configs[0], TeamConfig)
        self.assertIsInstance(team_configs[1], TeamConfig)
        
        # Test first team gets workflow defaults
        team1 = team_configs[0]
        self.assertEqual(team1.id, 'team1')
        self.assertEqual(team1.model, 'gpt-4o-mini')  # From workflow default
        self.assertEqual(team1.temperature, 0.3)  # From workflow default
        self.assertEqual(team1.max_messages, 50)  # From workflow default
        self.assertEqual(team1.allow_repeated_speaker, False)  # From workflow default
        self.assertEqual(team1.max_selector_attempts, 3)  # From workflow default
        self.assertEqual(team1.termination_keyword, 'TERMINATE')  # From workflow default
        self.assertEqual(team1.input_files, [])  # Default empty list
        self.assertEqual(team1.step_files, [])  # Default empty list
        self.assertIsNone(team1.agent_result)  # Default None
        self.assertIsNone(team1.depends_on)  # Default None
        
        # Test second team overrides and custom values
        team2 = team_configs[1]
        self.assertEqual(team2.id, 'team2')
        self.assertEqual(team2.model, 'gpt-4')  # Team override
        self.assertEqual(team2.temperature, 0.7)  # Team override
        self.assertEqual(team2.max_messages, 50)  # From workflow default
        self.assertEqual(team2.input_files, ['custom_input.md'])  # Custom value
        self.assertEqual(team2.step_files, [])  # Default empty list
        
    def test_load_workflow_from_file(self):
        """Test loading workflow from file"""
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.test_workflow_data, f)
            temp_file_path = f.name
        
        try:
            team_configs = AssetUtils.load_workflow(temp_file_path)
            
            # Should return 2 TeamConfig objects
            self.assertEqual(len(team_configs), 2)
            self.assertIsInstance(team_configs[0], TeamConfig)
            self.assertIsInstance(team_configs[1], TeamConfig)
            
            # Test first team
            team1 = team_configs[0]
            self.assertEqual(team1.id, 'team1')
            self.assertEqual(team1.model, 'gpt-4o-mini')
            
            # Test second team
            team2 = team_configs[1]
            self.assertEqual(team2.id, 'team2')
            self.assertEqual(team2.model, 'gpt-4')  # Override
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    def test_missing_workflow_section(self):
        """Test error handling for missing workflow section"""
        invalid_data = {'invalid': 'data'}
        
        with self.assertRaises(ValueError) as context:
            AssetUtils.load_workflow_from_dict(invalid_data)
        
        self.assertIn("missing 'workflow' section", str(context.exception))
    
    def test_missing_teams_section(self):
        """Test error handling for missing teams section"""
        invalid_data = {'workflow': {'model': 'gpt-4o-mini'}}
        
        with self.assertRaises(ValueError) as context:
            AssetUtils.load_workflow_from_dict(invalid_data)
        
        self.assertIn("missing 'teams' section", str(context.exception))
    
    def test_missing_required_team_fields(self):
        """Test error handling for missing required team fields"""
        # Missing 'id' field
        invalid_data = {
            'workflow': {
                'teams': [{'template': 'template1.yaml', 'output_file': 'output1.md'}]
            }
        }
        
        with self.assertRaises(ValueError) as context:
            AssetUtils.load_workflow_from_dict(invalid_data)
        
        self.assertIn("missing required 'id' field", str(context.exception))
        
        # Missing 'template' field
        invalid_data = {
            'workflow': {
                'teams': [{'id': 'team1', 'output_file': 'output1.md'}]
            }
        }
        
        with self.assertRaises(ValueError) as context:
            AssetUtils.load_workflow_from_dict(invalid_data)
        
        self.assertIn("missing required 'template' field", str(context.exception))
        
        # Missing 'output_file' field
        invalid_data = {
            'workflow': {
                'teams': [{'id': 'team1', 'template': 'template1.yaml'}]
            }
        }
        
        with self.assertRaises(ValueError) as context:
            AssetUtils.load_workflow_from_dict(invalid_data)
        
        self.assertIn("missing required 'output_file' field", str(context.exception))
    
    def test_file_not_found(self):
        """Test error handling for missing file"""
        with self.assertRaises(FileNotFoundError) as context:
            AssetUtils.load_workflow('/nonexistent/file.yaml')
        
        self.assertIn("Workflow file not found", str(context.exception))
    
    def test_workflow_without_defaults(self):
        """Test workflow with no workflow-level defaults"""
        minimal_data = {
            'workflow': {
                'teams': [
                    {
                        'id': 'team1',
                        'template': 'template1.yaml',
                        'output_file': 'output1.md',
                        'model': 'gpt-3.5-turbo'
                    }
                ]
            }
        }
        
        team_configs = AssetUtils.load_workflow_from_dict(minimal_data)
        
        self.assertEqual(len(team_configs), 1)
        self.assertIsInstance(team_configs[0], TeamConfig)
        team1 = team_configs[0]
        self.assertEqual(team1.model, 'gpt-3.5-turbo')
        self.assertIsNone(team1.temperature)  # No workflow default
        self.assertEqual(team1.input_files, [])  # Still gets required field defaults


if __name__ == '__main__':
    unittest.main()
