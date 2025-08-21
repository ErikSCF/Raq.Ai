#!/usr/bin/env python3
"""
Process Analysis Runner for Document Generation Service

This module runs the Process Analysis Team on job folders,
allowing analysis of workflow patterns and optimization suggestions.
"""

import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# AutoGen imports
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.base import OrTerminationCondition
import yaml

class ProcessAnalysisRunner:
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.process_analysis_yaml = self.base_dir / "Process_Analysis_Team.yaml"
    
    def validate_pipeline_folder(self, folder_path: str) -> tuple[bool, str]:
        """Validate that the pipeline folder contains required files."""
        folder = Path(folder_path)
        if not folder.exists():
            return False, f"Folder does not exist: {folder_path}"
        
        # Check for required files
        required_files = [
            "pipeline_config.json",
            "planning_output_steps.md",
            "production_output_steps.md"
        ]
        
        missing_files = []
        for file_name in required_files:
            file_path = folder / file_name
            if not file_path.exists():
                missing_files.append(file_name)
        
        if missing_files:
            return False, f"Missing required files: {', '.join(missing_files)}"
        
        return True, "Pipeline folder is valid"
    
    def load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML file and return parsed data."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def read_pipeline_folder_contents(self, folder_path: str) -> Dict[str, Any]:
        """Read all relevant files from the pipeline folder."""
        folder = Path(folder_path)
        contents = {}
        
        # Read pipeline configuration
        config_file = folder / "pipeline_config.json"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                contents['config'] = json.load(f)
        
        # Read conversation steps
        planning_steps = folder / "planning_output_steps.md"
        if planning_steps.exists():
            with open(planning_steps, 'r', encoding='utf-8') as f:
                contents['planning_steps'] = f.read()
        
        production_steps = folder / "production_output_steps.md"
        if production_steps.exists():
            with open(production_steps, 'r', encoding='utf-8') as f:
                contents['production_steps'] = f.read()
        
        # Read final outputs
        planning_output = folder / "planning_output.md"
        if planning_output.exists():
            with open(planning_output, 'r', encoding='utf-8') as f:
                contents['planning_output'] = f.read()
        
        production_output = folder / "production_output.md"
        if production_output.exists():
            with open(production_output, 'r', encoding='utf-8') as f:
                contents['production_output'] = f.read()
        
        # Read content brief if available
        brief_files = list(folder.glob("content_brief_*"))
        if brief_files:
            with open(brief_files[0], 'r', encoding='utf-8') as f:
                contents['content_brief'] = f.read()
        
        return contents
    
    def extract_agent_flow_from_steps(self, steps_content: str) -> str:
        """Extract just the agent interaction flow from conversation steps."""
        if not steps_content:
            return "No conversation steps found"
        
        lines = steps_content.split('\n')
        agent_interactions = []
        
        # Define non-agent entries to filter out
        non_agents = {'user', 'System', 'Pros', 'Cons', 'TaskResult', 'FunctionCall', 'FunctionExecutionResult'}
        
        for line in lines:
            agent_name = None
            
            if line.strip().startswith('**') and '**:' in line:
                # Old format: **agent_name**:
                start = line.find('**') + 2
                end = line.find('**', start)
                if end > start:
                    agent_name = line[start:end].strip()
            elif line.strip().startswith('*AGENT:') and line.strip().endswith('*'):
                # New format: *AGENT: agent_name*
                agent_part = line.strip()[7:-1].strip()  # Remove *AGENT: and final *
                agent_name = agent_part
            
            if agent_name and agent_name not in non_agents:
                agent_interactions.append(agent_name)
        
        if agent_interactions:
            # Create a simple flow representation
            flow = ' → '.join(agent_interactions)
            return f"Agent Flow: user → {flow}"
        else:
            return "No agent interactions found"
    
    def prepare_analysis_task_message(self, folder_path: str, contents: Dict[str, Any]) -> str:
        """Prepare the task message for process analysis."""
        task_parts = [
            f"=== AGENT WORKFLOW ANALYSIS REQUEST ===",
            f"Pipeline Folder: {folder_path}",
            f"\nAnalyze the agent-to-agent workflow patterns below.",
            f"Focus on identifying the agent interaction flow and any workflow patterns or issues."
        ]
        
        if 'planning_steps' in contents:
            planning_flow = self.extract_agent_flow_from_steps(contents['planning_steps'])
            task_parts.append(f"\n=== PLANNING TEAM WORKFLOW ===")
            task_parts.append(planning_flow)
        
        if 'production_steps' in contents:
            production_flow = self.extract_agent_flow_from_steps(contents['production_steps'])
            task_parts.append(f"\n=== PRODUCTION TEAM WORKFLOW ===")
            task_parts.append(production_flow)
        
        task_parts.append(f"\nProvide analysis of the workflow patterns, efficiency, and any recommendations.")
        
        return "\n".join(task_parts)
    
    async def run_process_analysis(self, folder_path: str, output_file: Optional[str] = None) -> bool:
        """Run the Process Analysis Team on the specified folder."""
        print(f"=== Process Analysis Runner ===")
        print(f"Analyzing pipeline folder: {folder_path}")
        
        # Validate folder
        is_valid, message = self.validate_pipeline_folder(folder_path)
        if not is_valid:
            print(f"Error: {message}")
            return False
        
        print(f"✓ Pipeline folder validated: {message}")
        
        # Read folder contents
        contents = self.read_pipeline_folder_contents(folder_path)
        print(f"✓ Read {len(contents)} files from pipeline folder")
        
        # Load Process Analysis Team configuration
        if not self.process_analysis_yaml.exists():
            print(f"Error: Process Analysis Team configuration not found: {self.process_analysis_yaml}")
            return False
        
        try:
            team_config = self.load_yaml_file(self.process_analysis_yaml)
            print(f"✓ Loaded Process Analysis Team configuration")
            
            # Create model client
            model_client = OpenAIChatCompletionClient(
                model=team_config.get('config', {}).get('model', 'gpt-4o-mini')
            )
            
            # Create agents dynamically from YAML config
            agents = {}
            for participant in team_config['participants']:
                agent_name = participant['name']
                agent_config = {
                    'description': participant.get('description', ''),
                    'system_message': participant.get('system_message', ''),
                    'model_client': model_client
                }
                
                # Create the agent
                agent = AssistantAgent(name=agent_name, **agent_config)
                agents[agent_name] = agent
            
            print(f"✓ Created {len(agents)} agents: {list(agents.keys())}")
            
            # Create team with selector
            termination_keyword = team_config.get('config', {}).get('termination_keyword', 'TERMINATE')
            team = SelectorGroupChat(
                participants=list(agents.values()),
                termination_condition=OrTerminationCondition(
                    MaxMessageTermination(team_config.get('config', {}).get('max_messages', 10)),
                    TextMentionTermination(termination_keyword)
                ),
                model_client=model_client,
                selector_prompt=team_config['team']['selector_prompt']
            )
            
            # Prepare task message
            task_message = self.prepare_analysis_task_message(folder_path, contents)
            
            # Determine output file
            if not output_file:
                folder = Path(folder_path)
                output_file = str(folder / "process_analysis.md")
            
            # Run the team and collect output
            clean_output_content = []
            raw_output_content = []
            final_markdown_content = None
            
            print(f"✓ Starting Process Analysis Team execution...")
            
            async for message in team.run_stream(task=task_message):
                # Always save raw message for debugging
                raw_content = f"**Raw Message**: {str(message)}\n\n"
                raw_output_content.append(raw_content)
                
                # Extract clean content from various message types
                clean_content = None
                source_name = "System"
                
                if hasattr(message, 'source') and hasattr(message, 'content'):
                    clean_content = message.content
                    source_name = message.source
                elif hasattr(message, 'content'):
                    clean_content = message.content
                    source_name = getattr(message, 'source', 'Unknown')
                elif hasattr(message, 'text'):
                    clean_content = message.text
                    source_name = getattr(message, 'source', 'System')
                else:
                    message_type = type(message).__name__
                    clean_content = f"[{message_type} event]"
                    source_name = "System"
                
                if clean_content:
                    # Use the same formatting as pipeline runner
                    content = f"---\n*AGENT: {source_name}*\n--- \n\n {clean_content}\n\n"
                    clean_output_content.append(content)
                    print(f"[{source_name}]: {clean_content[:100]}...")
                    
                    # Check if this is the markdown agent's final output
                    if source_name == 'markdown_agent':
                        # Check for markdown blocks first
                        if clean_content.strip().startswith('```markdown'):
                            lines = clean_content.strip().split('\n')
                            if lines[0] == '```markdown' and lines[-1] == '```':
                                final_markdown_content = '\n'.join(lines[1:-1])
                            elif lines[0] == '```markdown':
                                content_lines = []
                                for line in lines[1:]:
                                    if line.strip() == '```':
                                        break
                                    content_lines.append(line)
                                final_markdown_content = '\n'.join(content_lines)
                        else:
                            # Handle direct markdown content (not wrapped in code blocks)
                            final_markdown_content = clean_content.strip()
            
            # Save outputs
            output_path = Path(output_file)
            steps_file = output_path.parent / f"{output_path.stem}_steps{output_path.suffix}"
            raw_file = output_path.parent / f"{output_path.stem}_raw{output_path.suffix}"
            
            # Save conversation steps
            clean_output = "".join(clean_output_content)
            with open(steps_file, 'w', encoding='utf-8') as f:
                f.write(clean_output)
            
            # Save raw debugging data
            raw_output = "".join(raw_output_content)
            with open(raw_file, 'w', encoding='utf-8') as f:
                f.write(raw_output)
            
            # Save final markdown content
            if final_markdown_content:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(final_markdown_content)
                print(f"✓ Process analysis final output saved to: {output_path}")
                print(f"✓ Process analysis conversation steps saved to: {steps_file}")
                print(f"✓ Process analysis raw debugging data saved to: {raw_file}")
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(clean_output)
                print(f"✓ Process analysis completed and saved (no markdown agent output detected)")
                print(f"✓ Process analysis conversation steps saved to: {steps_file}")
                print(f"✓ Process analysis raw debugging data saved to: {raw_file}")
            
            return True
            
        except Exception as e:
            print(f"✗ Error running Process Analysis: {e}")
            import traceback
            traceback.print_exc()
            return False
