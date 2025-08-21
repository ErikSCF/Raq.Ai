#!/usr/bin/env python3
"""
Pipeline Runner for Document Generation Service

This module contains the core AutoGen pipeline logic that runs Content Planning Team,
Content Production Team, and Process Analysis using the job ID as the version number.

Features:
- Job-based execution using provided job ID
- Sequential execution: Planning Team -> Production Team -> Process Analysis
- Output saved to job-specific directories
- Integrated with DocumentGenerationService
"""

import yaml
import json
import sys
import shutil
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

# AutoGen imports
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.base import OrTerminationCondition
from autogen_core.tools import FunctionTool
from autogen_core.tools import StaticWorkbench

# Import the Process Analysis Runner
try:
    from process_analysis_runner import ProcessAnalysisRunner
except ImportError:
    # Fallback for when running in different contexts
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from process_analysis_runner import ProcessAnalysisRunner

class PipelineRunner:
    def __init__(self, base_dir: Path = None, cancellation_flag=None):
        self.base_dir = base_dir or Path(__file__).parent
        self.content_briefs_dir = self.base_dir / "content_briefs"
        self.tools_config_path = self.base_dir / "tools_config.yaml"
        self.cancellation_flag = cancellation_flag  # For checking cancellation during execution
        self.brief_content = ""  # Store content brief for appending to final output
        
        # Team configuration files
        self.planning_yaml = self.base_dir / "Content_Planning_Team.yaml"
        self.production_yaml = self.base_dir / "Content_Production_Team.yaml"
        
        # Initialize the Process Analysis Runner
        self.process_analysis_runner = ProcessAnalysisRunner(self.base_dir)
    
    def create_job_folder(self, job_id: str, output_base_path: Path) -> Path:
        """Create a job-specific folder."""
        job_folder = output_base_path / job_id
        job_folder.mkdir(parents=True, exist_ok=True)
        return job_folder
    
    def load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML file and return parsed data."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def copy_assets(self, job_folder: Path, content_brief_type: str, template_url: Optional[str], user_input: str, custom_content_brief: Optional[str] = None):
        """Copy all relevant assets to the job folder."""
        
        # Copy YAML files
        planning_yaml_dest = job_folder / "Content_Planning_Team.yaml"
        production_yaml_dest = job_folder / "Content_Production_Team.yaml"
        
        shutil.copy2(self.planning_yaml, planning_yaml_dest)
        shutil.copy2(self.production_yaml, production_yaml_dest)
        
        # Handle content brief
        print(f"DEBUG: copy_assets called with content_brief_type='{content_brief_type}', custom_content_brief={custom_content_brief is not None}")
        
        if custom_content_brief:
            # Save custom content brief
            brief_dest = job_folder / "content_brief_custom.md"
            with open(brief_dest, 'w', encoding='utf-8') as f:
                f.write(custom_content_brief)
            print(f"Saved custom content brief to: {brief_dest}")
            
            # Also save as the standard name that agents expect to reference
            standard_brief_dest = job_folder / "brand_content_brief.md"
            with open(standard_brief_dest, 'w', encoding='utf-8') as f:
                f.write(custom_content_brief)
            print(f"Saved content brief as: {standard_brief_dest}")
            
        elif content_brief_type:
            # Copy existing content brief if specified
            # Convert hyphenated type back to filename format with underscores
            brief_file = f"{content_brief_type.replace('-', '_')}.md"
            brief_source = self.content_briefs_dir / brief_file
            print(f"DEBUG: Looking for content brief file: {brief_source}")
            print(f"DEBUG: File exists: {brief_source.exists()}")
            
            if brief_source.exists():
                brief_dest = job_folder / f"content_brief_{brief_file}"
                shutil.copy2(brief_source, brief_dest)
                print(f"DEBUG: Copied to: {brief_dest}")
                
                # Also save as the standard name that agents expect to reference
                standard_brief_dest = job_folder / "brand_content_brief.md"
                shutil.copy2(brief_source, standard_brief_dest)
                print(f"Saved content brief as: {standard_brief_dest}")
            else:
                print(f"Warning: Content brief file not found: {brief_source}")
                print(f"Available files: {list(self.content_briefs_dir.glob('*.md'))}")
        else:
            print("DEBUG: No content brief type specified")
        
        # Create pipeline configuration file
        config_data = {
            "job_id": job_folder.name,
            "content_brief_type": content_brief_type,
            "template_url": template_url,
            "user_input": user_input,
            "custom_content_brief": custom_content_brief is not None,
            "timestamp": datetime.now().isoformat()
        }
        
        config_file = job_folder / "pipeline_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        print(f"Copied assets to: {job_folder}")
        return planning_yaml_dest, production_yaml_dest
    
    async def run_autogen_team(self, yaml_config_path: Path, output_file_path: Path, team_name: str, input_data: Optional[Dict[str, Any]] = None, job_folder: Path = None) -> bool:
        """Run AutoGen team using YAML configuration to dynamically create agents and team."""
        print(f"\n=== Running {team_name} ===")
        
        print(f"Team configuration: {yaml_config_path}")
        print(f"Output will be saved to: {output_file_path}")
        if input_data:
            print(f"Input data provided: {list(input_data.keys())}")
        
        try:
            # Load the YAML configuration
            team_config = self.load_yaml_file(yaml_config_path)
            
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
                
                # Add tools if specified
                if participant.get('tools'):
                    tools_config = self.load_yaml_file(self.tools_config_path)
                    workbench_tools = []
                    
                    for tool_name in participant['tools']:
                        if tool_name in tools_config['tools']:
                            tool_config = tools_config['tools'][tool_name]
                            
                            # Execute the source code to create the function
                            exec_globals = {}
                            exec(tool_config['source_code'], exec_globals)
                            
                            # Get the function from the executed code
                            function_name = tool_config.get('name', tool_name)
                            if function_name in exec_globals:
                                func = exec_globals[function_name]
                                
                                # Create function tool
                                function_tool = FunctionTool(
                                    func=func,
                                    name=function_name,
                                    description=tool_config.get('description', '')
                                )
                                workbench_tools.append(function_tool)
                    
                    if workbench_tools:
                        agent_config['workbench'] = StaticWorkbench(tools=workbench_tools)
                
                # Create the agent
                agent = AssistantAgent(name=agent_name, **agent_config)
                agents[agent_name] = agent
            
            # Create team with selector
            team = SelectorGroupChat(
                participants=list(agents.values()),
                termination_condition=OrTerminationCondition(
                    MaxMessageTermination(team_config.get('config', {}).get('max_messages', 50)),
                    TextMentionTermination("TERMINATE")
                ),
                model_client=model_client,
                selector_prompt=team_config['team']['selector_prompt']
            )
            
            # Prepare task message from input data
            task_message = self.prepare_task_message(input_data, team_name, job_folder)
            
            # Run the team and collect output
            clean_output_content = []  # For readable conversation steps
            raw_output_content = []    # For raw debugging data
            final_markdown_content = None
            print(f"Starting {team_name} execution...")
            
            async for message in team.run_stream(task=task_message):
                # Always save raw message for debugging
                raw_content = f"**Raw Message**: {str(message)}\n\n"
                raw_output_content.append(raw_content)
                
                # Extract clean content from various message types
                clean_content = None
                source_name = "System"
                
                if hasattr(message, 'source') and hasattr(message, 'content'):
                    # Standard message with source and content
                    clean_content = message.content
                    source_name = message.source
                elif hasattr(message, 'content'):
                    # Message with content but no source
                    clean_content = message.content
                    source_name = getattr(message, 'source', 'Unknown')
                elif hasattr(message, 'text'):
                    # Some messages might use 'text' instead of 'content'
                    clean_content = message.text
                    source_name = getattr(message, 'source', 'System')
                else:
                    # For non-standard messages, include basic info in clean output
                    message_type = type(message).__name__
                    clean_content = f"[{message_type} event]"
                    source_name = "System"
                
                if clean_content:
                    # Save clean readable content
                    content = f"---\n*AGENT: {source_name}*\n--- \n\n {clean_content}\n\n"
                    clean_output_content.append(content)
                    print(f"[{source_name}]: {clean_content[:100]}...")
                    
                    # Check if this is the markdown agent's final output
                    if source_name == 'markdown_agent':
                        # The markdown agent outputs the final content, possibly wrapped in code blocks
                        content = clean_content.strip()
                        
                        # Remove markdown code block wrapper if present
                        if content.startswith('```markdown'):
                            lines = content.split('\n')
                            # Remove first line (```markdown) and find end
                            content_lines = []
                            in_content = False
                            for line in lines:
                                if line.strip() == '```markdown':
                                    in_content = True
                                    continue
                                elif line.strip() == '```' or line.strip() == 'TERMINATE':
                                    break
                                elif in_content:
                                    content_lines.append(line)
                            final_markdown_content = '\n'.join(content_lines).strip()
                        else:
                            # Remove any trailing TERMINATE
                            final_markdown_content = content.replace('TERMINATE', '').strip()
                        
                        # Append content brief to the final markdown content if available and in planning phase
                        if hasattr(self, 'brief_content') and self.brief_content and 'Planning' in team_name:
                            final_markdown_content += f"\n\n<!--- SECTION: CONTENT BRIEF --->\n\n{self.brief_content}\n<!--- END SECTION: CONTENT BRIEF  --->"
            
            # Save the clean conversation steps
            steps_file = output_file_path.parent / f"{output_file_path.stem}_steps{output_file_path.suffix}"
            clean_output = "".join(clean_output_content)
            with open(steps_file, 'w', encoding='utf-8') as f:
                f.write(clean_output)
            
            # Save the raw debugging data
            raw_file = output_file_path.parent / f"{output_file_path.stem}_raw{output_file_path.suffix}"
            raw_output = "".join(raw_output_content)
            with open(raw_file, 'w', encoding='utf-8') as f:
                f.write(raw_output)
            
            # Save the final markdown content if we have it
            if final_markdown_content:
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(final_markdown_content)
                print(f"✓ {team_name} final output saved to: {output_file_path}")
                print(f"✓ {team_name} conversation steps saved to: {steps_file}")
                print(f"✓ {team_name} raw debugging data saved to: {raw_file}")
            else:
                # Fallback: save the clean conversation if no markdown agent output found
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(clean_output)
                print(f"✓ {team_name} execution completed and saved (no markdown agent output detected)")
                print(f"✓ {team_name} conversation steps saved to: {steps_file}")
                print(f"✓ {team_name} raw debugging data saved to: {raw_file}")
            return True
            
        except Exception as e:
            print(f"✗ Error running {team_name}: {e}")
            import traceback
            traceback.print_exc()
            
            # Create error output file
            error_content = f"""# {team_name} - Execution Error

An error occurred while running {team_name}:

**Error**: {str(e)}
**Timestamp**: {datetime.now().isoformat()}
**Configuration**: {yaml_config_path}

## Troubleshooting

1. Check that the YAML configuration file is valid
2. Verify all required dependencies are installed
3. Ensure input data is properly formatted
4. Review the error message above for specific details

## Full Error Details
{traceback.format_exc()}
"""
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(error_content)
            
            return False
    
    def prepare_task_message(self, input_data: Optional[Dict[str, Any]], team_name: str, job_folder: Path = None) -> str:
        """Prepare the initial task message for the AutoGen team."""
        if not input_data:
            return f"Please begin the {team_name} workflow."
        
        # Extract key information from input data
        content_brief_type = input_data.get('content_brief_type', 'Unknown')
        user_input = input_data.get('user_input', 'Unknown')
        template_url = input_data.get('template_url')
        has_custom_brief = input_data.get('custom_content_brief', False)
        
        # Read the content brief file if available
        self.brief_content = ""
        
        # Check for custom content brief first
        if job_folder and has_custom_brief:
            custom_brief_path = job_folder / "content_brief_custom.md"
            if custom_brief_path.exists():
                with open(custom_brief_path, 'r', encoding='utf-8') as f:
                    self.brief_content = f.read()
                print(f"Using custom content brief from: {custom_brief_path}")
        elif content_brief_type != 'Unknown':
            # Fallback to original content brief
            # Convert hyphenated type back to filename format with underscores
            brief_file = f"{content_brief_type.replace('-', '_')}.md"
            brief_path = self.content_briefs_dir / brief_file
            if brief_path.exists():
                with open(brief_path, 'r', encoding='utf-8') as f:
                    self.brief_content = f.read()
                print(f"Using default content brief: {content_brief_type}")
            else:
                print(f"Warning: Content brief file not found: {brief_path}")
                print(f"Available files: {list(self.content_briefs_dir.glob('*.md'))}")
        
        # Prepare task message based on team type
        if 'Planning' in team_name:
            task_parts = [
                f"Content Description: {user_input}",
                f"Content Brief Type: {content_brief_type if not has_custom_brief else 'Custom'}"
            ]
            
            if self.brief_content:
                task_parts.append(f"\nSTART CONTENT BRIEF:\n{self.brief_content}")
                task_parts.append(f"\nEND CONTENT BRIEF")
            
            if template_url:
                task_parts.append(f"\nSource URL for structure analysis: {template_url}")
            
            task_parts.append("\nPlease begin the content planning workflow to create article outline, SEO keywords, research data, introduction, and brand-aligned planning artifacts.")
            task_parts.append("\nIMPORTANT: All agents should reference the brand_content_brief.md file for guidance on brand voice, target audience, content strategy, and any specific requirements or formatting instructions.")
            
        elif 'Production' in team_name:
            planning_artifacts = input_data.get('planning_artifacts', '')
            if planning_artifacts and Path(planning_artifacts).exists():
                with open(planning_artifacts, 'r', encoding='utf-8') as f:
                    planning_content = f.read()
                    
                # Remove any TERMINATE text from planning content to prevent premature termination
                planning_content = planning_content.replace('TERMINATE', '').strip()
                
                task_parts = [
                    f"Content Brief Type: {content_brief_type if not has_custom_brief else 'Custom'}",
                    f"\nPLANNING ARTIFACTS:\n{planning_content}",
                    "\nPlease begin the content production workflow to create the final article based on the planning artifacts above."
                ]
            else:
                task_parts = [
                    f"Content Brief Type: {content_brief_type if not has_custom_brief else 'Custom'}",
                    f"Content Description: {user_input}",
                    "\nPlease begin the content production workflow to create the final article."
                ]
        else:
            # Fallback for other team types
            task_parts = [
                f"Content Brief Type: {content_brief_type if not has_custom_brief else 'Custom'}",
                f"Content Description: {user_input}",
                f"\nPlease begin the {team_name} workflow."
            ]
        
        return "\n".join(task_parts)
    
    async def run_pipeline(self, job_id: str, user_input: str, template_url: Optional[str], content_brief_type: str, output_base_path: Path, custom_content_brief: Optional[str] = None) -> bool:
        """Run the complete pipeline for a specific job."""
        print(f"=== AutoGen Pipeline Runner ===")
        print(f"Job ID: {job_id}")
        
        # Check required files
        missing_files = []
        required_files = [
            self.planning_yaml,
            self.production_yaml,
            self.tools_config_path
        ]
        
        for file_path in required_files:
            if not file_path.exists():
                missing_files.append(str(file_path))
        
        if missing_files:
            print("Error: The following required files were not found:")
            for file_path in missing_files:
                print(f"  - {file_path}")
            return False
        
        # Create job folder
        job_folder = self.create_job_folder(job_id, output_base_path)
        
        # Copy assets
        planning_yaml_dest, production_yaml_dest = self.copy_assets(
            job_folder, content_brief_type, template_url, user_input, custom_content_brief
        )
        
        # Run Planning Team
        planning_output = job_folder / "planning_output.md"
        success = await self.run_autogen_team(
            planning_yaml_dest, 
            planning_output, 
            "Content Planning Team",
            {
                "content_brief_type": content_brief_type,
                "template_url": template_url,
                "user_input": user_input,
                "custom_content_brief": custom_content_brief is not None
            },
            job_folder
        )
        
        if not success:
            print("Error: Planning team execution failed")
            return False
        
        # Check for cancellation after Planning Team
        if self.cancellation_flag and self.cancellation_flag.is_set():
            print("⚠️ Job cancelled after Content Planning Team execution")
            return False
        
        # Run Production Team (using planning output as input)
        production_output = job_folder / "production_output.md"
        success = await self.run_autogen_team(
            production_yaml_dest, 
            production_output, 
            "Content Production Team",
            {
                "planning_artifacts": str(planning_output),
                "content_brief_type": content_brief_type,
                "custom_content_brief": custom_content_brief is not None
            },
            job_folder
        )
        
        if not success:
            print("Error: Production team execution failed")
            return False
        
        # Check for cancellation after Production Team
        if self.cancellation_flag and self.cancellation_flag.is_set():
            print("⚠️ Job cancelled after Content Production Team execution")
            return False
        
        try:
            print("Running process analysis on the complete workflow...")
            
            # Check for cancellation before Process Analysis
            if self.cancellation_flag and self.cancellation_flag.is_set():
                print("⚠️ Job cancelled before Process Analysis execution")
                return False
            
            success = await self.process_analysis_runner.run_process_analysis(str(job_folder))
            if success:
                print("✓ Process Analysis completed successfully")
            else:
                print("Warning: Process analysis execution failed, but pipeline will continue")
        except Exception as e:
            print(f"Warning: Process analysis runner error: {e}")
            # Don't fail the entire pipeline if process analysis fails
        
        # Final cancellation check before completion
        if self.cancellation_flag and self.cancellation_flag.is_set():
            print("⚠️ Job cancelled during final processing")
            return False
        
        print(f"\n=== Pipeline Complete ===")
        print(f"Job ID: {job_id}")
        print(f"Job folder: {job_folder}")
        print(f"Planning output: {planning_output}")
        print(f"Production output: {production_output}")
        print(f"Process analysis: {job_folder / 'process_analysis.md'}")
        print(f"\n✨ Three-team pipeline completed successfully!")
        print(f"📊 Check the process analysis for workflow insights and optimization suggestions.")
        
        return True

    def run_production_only(self, job_id: str, planning_file_path: str) -> bool:
        """
        Run only the content production workflow using provided planning output.
        
        This method skips the planning phase and directly executes the Content Production Team
        using the provided planning_output.md file as input.
        
        Args:
            job_id: Unique identifier for the job
            planning_file_path: Path to the planning_output.md file
            
        Returns:
            bool: True if successful, False otherwise
        """
        print(f"=== AutoGen Production-Only Pipeline ===")
        print(f"Job ID: {job_id}")
        print(f"Planning Input: {planning_file_path}")
        
        try:
            # Determine paths
            job_folder = Path(planning_file_path).parent
            planning_output = Path(planning_file_path)
            
            # Verify planning file exists
            if not planning_output.exists():
                print(f"Error: Planning file not found: {planning_file_path}")
                return False
            
            # Check for cancellation before starting
            if self.cancellation_flag and self.cancellation_flag.is_set():
                print("⚠️ Job cancelled before production execution")
                return False
            
            # Copy required assets for production team
            production_yaml_dest = self._copy_production_assets(job_folder)
            
            # Run Production Team only (using provided planning output as input)
            production_output = job_folder / "production_output.md"
            success = asyncio.run(self.run_autogen_team(
                production_yaml_dest, 
                production_output, 
                "Content Production Team",
                {
                    "planning_artifacts": str(planning_output),
                    "content_brief_type": "custom",
                    "custom_content_brief": True
                },
                job_folder
            ))
            
            if not success:
                print("Error: Production team execution failed")
                return False
            
            # Check for cancellation after Production Team
            if self.cancellation_flag and self.cancellation_flag.is_set():
                print("⚠️ Job cancelled after Content Production Team execution")
                return False
            
            print(f"\n=== Production-Only Pipeline Complete ===")
            print(f"Job ID: {job_id}")
            print(f"Job folder: {job_folder}")
            print(f"Planning input: {planning_output}")
            print(f"Production output: {production_output}")
            print(f"\n✨ Production-only pipeline completed successfully!")
            
            return True
            
        except Exception as e:
            print(f"Error in production-only pipeline: {e}")
            return False
    
    def _copy_production_assets(self, job_folder: Path) -> Path:
        """Copy only the assets needed for production team execution."""
        try:
            # Copy production team YAML
            production_yaml_dest = job_folder / "Content_Production_Team.yaml"
            shutil.copy2(self.production_yaml, production_yaml_dest)
            
            # Copy tools config
            tools_config_dest = job_folder / "tools_config.yaml"
            shutil.copy2(self.tools_config_path, tools_config_dest)
            
            # Note: In production-only mode, we don't extract brand content brief
            # since it's already included in the planning output file that will be used
            
            return production_yaml_dest
            
        except Exception as e:
            print(f"Error copying production assets: {e}")
            raise
    
    
    def _extract_brand_brief_from_planning(self, planning_file: Path, job_folder: Path):
        """Extract brand content brief from planning output for production team use."""
        try:
            with open(planning_file, 'r', encoding='utf-8') as f:
                planning_content = f.read()
            
            # Look for brand content brief section
            lines = planning_content.split('\n')
            brief_lines = []
            in_brief_section = False
            
            for line in lines:
                if "START CONTENT BRIEF" in line.upper():
                    in_brief_section = True
                    continue
                elif in_brief_section and line.strip() == "END CONTENT BRIEF":
                    break
                elif in_brief_section:
                    brief_lines.append(line)
            
            # Save extracted brief
            if brief_lines:
                brand_brief_path = job_folder / "brand_content_brief.md"
                with open(brand_brief_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(brief_lines).strip())
                print(f"✓ Extracted brand content brief to {brand_brief_path}")
            
        except Exception as e:
            print(f"Warning: Could not extract brand content brief: {e}")

    async def run_planning_only(self, job_id: str, user_input: str, template_url: Optional[str], content_brief_type: str, output_base_path: Path, custom_content_brief: Optional[str] = None) -> bool:
        """Run only the planning pipeline for a specific job."""
        print(f"=== AutoGen Planning Pipeline Runner ===")
        print(f"Job ID: {job_id}")
        
        # Check required files
        missing_files = []
        required_files = [
            self.planning_yaml,
            self.tools_config_path
        ]
        
        for file_path in required_files:
            if not file_path.exists():
                missing_files.append(str(file_path))
        
        if missing_files:
            print("Error: The following required files were not found:")
            for file_path in missing_files:
                print(f"  - {file_path}")
            return False
        
        # Create job folder
        job_folder = self.create_job_folder(job_id, output_base_path)
        
        # Copy assets (only planning-related assets)
        self.copy_assets(
            job_folder, content_brief_type, template_url, user_input, custom_content_brief
        )
        
        # Run Planning Team only
        planning_output = job_folder / "planning_output.md"
        success = await self.run_autogen_team(
            job_folder / "Content_Planning_Team.yaml", 
            planning_output, 
            "Content Planning Team",
            {
                "content_brief_type": content_brief_type,
                "user_input": user_input,
                "template_url": template_url,
                "custom_content_brief": custom_content_brief
            },
            job_folder
        )
        
        if not success:
            print("❌ Planning Team execution failed")
            return False
        
        print("✅ Planning pipeline completed successfully")
        print(f"Planning output saved to: {planning_output}")
        
        return True
