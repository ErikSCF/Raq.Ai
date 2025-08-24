#!/usr/bin/env python3
"""
Tests for Team

Test the Team class functionality.
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from team import Team, TeamConfig


class TestTeam(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = TeamConfig(
            name='TestTeam',
            output_file='test.md',
            depends_on='OtherTeam',
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
        self.team = Team(self.config)
    
    def test_team_creation_with_config(self):
        """Test creating a Team with a TeamConfig object"""
        self.assertIsInstance(self.team, Team)
        self.assertEqual(self.team.config, self.config)
    
    def test_workflow_properties(self):
        """Test workflow-related properties"""
        self.assertEqual(self.team.name, 'TestTeam')
        self.assertEqual(self.team.output_file, 'test.md')
        self.assertEqual(self.team.depends_on, 'OtherTeam')
        self.assertEqual(self.team.input_files, ['input.txt'])
        self.assertEqual(self.team.step_files, ['steps.md'])
        self.assertEqual(self.team.agent_result, 'result')
    
    def test_autogen_properties(self):
        """Test AutoGen-related properties"""
        self.assertEqual(self.team.model, 'gpt-4o-mini')
        self.assertEqual(self.team.temperature, 0.5)
        self.assertEqual(self.team.max_messages, 25)
        self.assertEqual(self.team.allow_repeated_speaker, True)
        self.assertEqual(self.team.max_selector_attempts, 5)
        self.assertEqual(self.team.termination_keyword, 'STOP')
    
    def test_string_representation(self):
        """Test string representations"""
        str_repr = str(self.team)
        self.assertIn('TestTeam', str_repr)
        self.assertIn('test.md', str_repr)
        self.assertIn('OtherTeam', str_repr)
        
        repr_str = repr(self.team)
        self.assertIn('Team(config=', repr_str)
    
    def test_team_with_minimal_config(self):
        """Test team with minimal configuration"""
        minimal_config = TeamConfig(
            name='MinimalTeam',
            output_file='minimal.md',
            depends_on=None,
            input_files=[],
            step_files=[],
            agent_result=None,
            model='gpt-4o-mini',
            temperature=0.3,
            max_messages=50,
            allow_repeated_speaker=False,
            max_selector_attempts=3,
            termination_keyword='TERMINATE'
        )
        
        minimal_team = Team(minimal_config)
        
        self.assertEqual(minimal_team.name, 'MinimalTeam')
        self.assertEqual(minimal_team.depends_on, None)
        self.assertEqual(minimal_team.input_files, [])
        self.assertEqual(minimal_team.step_files, [])
        self.assertEqual(minimal_team.agent_result, None)


if __name__ == "__main__":
    unittest.main()
