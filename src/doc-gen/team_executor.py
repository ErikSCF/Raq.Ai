#!/usr/bin/env python3
"""
Team Executor for Document Generation Pipeline

This module handles AutoGen team creation and execution.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# AutoGen imports
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.base import OrTerminationCondition
from autogen_core.tools import FunctionTool
from autogen_core.tools import StaticWorkbench

from task_builder import TaskBuilder


class TeamExecutor:
    """Handles AutoGen team creation and execution."""
    
    def __init__(self, base_dir: Path = None, workflow_manager=None):
        self.base_dir = base_dir or Path(__file__).parent
        self.tools_config_path = self.base_dir / "tools_config.yaml"
        self.task_builder = TaskBuilder()
        self.workflow_manager = workflow_manager
    
    async def execute_team(self, yaml_config_path: Path, output_file_path: Path, team_name: str, 
                          job_id: str, user_input: str, external_urls: Optional[List[str]], 
                          document_type: str, job_folder: Path = None, 
                          input_files: Optional[List[str]] = None, step_summaries: str = "", 
                          agent_result_content: str = "", memory=None, cancellation_flag=None) -> bool:
        """Execute AutoGen team using YAML configuration."""
        
        print(f"\n=== Running {team_name} ===")
        print(f"Team configuration: {yaml_config_path}")
        print(f"Output will be saved to: {output_file_path}")
        if input_files:
            print(f"Input files: {input_files}")
        if external_urls:
            print(f"External URLs: {external_urls}")
        
        try:
            # Get everything from workflow manager - it handles all YAML loading internally
            team_config = self.workflow_manager.get_team_config(team_name)
            
            # Extract values for AutoGen setup
            team_model = team_config['model']
            team_temperature = team_config['temperature']
            max_messages = team_config['max_messages']
            allow_repeated_speaker = team_config['allow_repeated_speaker']
            max_selector_attempts = team_config['max_selector_attempts']
            termination_keyword = team_config['termination_keyword']
            
            model_client = OpenAIChatCompletionClient(
                model=team_model,
                temperature=team_temperature
            )
            
            # Create agents - workflow manager provides agent structure too
            agents = self._create_agents(team_config, model_client, step_summaries, 
                                       agent_result_content, memory)
            
            # Get selector prompt from workflow manager
            selector_prompt = team_config['selector']['system_message']
            files_list = input_files if input_files is not None else []
            
            # Apply template variable replacements
            selector_prompt = self.task_builder.prepare_template_variables(
                selector_prompt, files_list, step_summaries, agent_result_content
            )

            # Create team with enhanced selector handling
            team = SelectorGroupChat(
                participants=list(agents.values()),
                termination_condition=OrTerminationCondition(
                    MaxMessageTermination(max_messages),
                    TextMentionTermination(termination_keyword)
                ),
                model_client=model_client,
                selector_prompt=selector_prompt,
                allow_repeated_speaker=allow_repeated_speaker,
                max_selector_attempts=max_selector_attempts
            )
            
            # Prepare task message
            brief_content = self.task_builder.load_content_brief(document_type, job_folder)
            task_message = self.task_builder.prepare_task_message(
                job_id, user_input, external_urls, document_type, team_name, 
                job_folder, input_files, asset_manager=None, brief_content=brief_content
            )
            
            # Execute team and handle output
            success = await self._execute_team_conversation(
                team, task_message, output_file_path, team_name, job_id, 
                brief_content, cancellation_flag, team_config
            )
            
            return success

        except Exception as e:
            print(f"✗ Error running {team_name}: {e}")
            import traceback
            traceback.print_exc()
            
            # Create error output file
            await self._create_error_output(output_file_path, team_name, job_id, 
                                          yaml_config_path, str(e), traceback.format_exc())
            
            return False
    
    def _create_agents(self, team_config: Dict[str, Any], model_client, step_summaries: str, 
                      agent_result_content: str, memory) -> Dict[str, AssistantAgent]:
        """Create agents dynamically from team config."""
        agents = {}
        
        # Get agents list from team config
        agents_config = team_config['agents']
        
        for agent_config in agents_config:
            agent_name = agent_config['name']
            
            # Get system message and inject context if needed
            system_message = agent_config.get('system_message', '')
            system_message = self.task_builder.inject_agent_context(
                system_message, step_summaries, agent_result_content
            )
            
            agent_setup = {
                'description': agent_config.get('description', ''),
                'system_message': system_message,
                'model_client': model_client
            }
            
            # Add tools if specified
            if agent_config.get('tools'):
                workbench_tools = self._create_agent_tools(agent_config['tools'])
                if workbench_tools:
                    agent_setup['workbench'] = StaticWorkbench(tools=workbench_tools)
            
            # Add memory if available and agent needs vector memory
            if memory and agent_config.get('vector_memory', False):
                agent_setup['memory'] = [memory]
                print(f"  ✓ {agent_name}: Vector memory enabled")
            elif agent_config.get('vector_memory', False):
                print(f"  ⚠ {agent_name}: Vector memory requested but not available")
            else:
                print(f"  - {agent_name}: Vector memory disabled")
            
            # Create the agent
            agent = AssistantAgent(name=agent_name, **agent_setup)
            agents[agent_name] = agent
        
        return agents
    
    def _create_agent_tools(self, tool_configs: List) -> List[FunctionTool]:
        """Create function tools from tool configurations."""
        workbench_tools = []
        
        for tool_item in tool_configs:
            if isinstance(tool_item, str):
                # Tool name reference - look up in tools config file
                with open(self.tools_config_path, 'r', encoding='utf-8') as f:
                    tools_config = yaml.safe_load(f)
                if tool_item in tools_config['tools']:
                    tool_config = tools_config['tools'][tool_item]
                    
                    # Execute the source code to create the function
                    exec_globals = {}
                    exec(tool_config['source_code'], exec_globals)
                    
                    # Get the function from the executed code
                    function_name = tool_config.get('name', tool_item)
                    if function_name in exec_globals:
                        func = exec_globals[function_name]
                        
                        # Create function tool
                        function_tool = FunctionTool(
                            func=func,
                            name=function_name,
                            description=tool_config.get('description', '')
                        )
                        workbench_tools.append(function_tool)
            elif isinstance(tool_item, dict):
                # Inline tool definition
                tool_name = tool_item.get('name')
                tool_function = tool_item.get('function')
                tool_description = tool_item.get('description', '')
                
                if tool_name and tool_function:
                    # Execute the function code to create the function
                    exec_globals = {}
                    exec(tool_function, exec_globals)
                    
                    # Get the function from the executed code
                    if tool_name in exec_globals:
                        func = exec_globals[tool_name]
                        
                        # Create function tool
                        function_tool = FunctionTool(
                            func=func,
                            name=tool_name,
                            description=tool_description
                        )
                        workbench_tools.append(function_tool)
        
        return workbench_tools
    
    async def _execute_team_conversation(self, team, task_message: str, output_file_path: Path, 
                                       team_name: str, job_id: str, brief_content: str, 
                                       cancellation_flag, team_config: dict) -> bool:
        """Execute team conversation and handle real-time output."""
        
        # Prepare file paths for real-time logging using new naming convention
        output_prefix = output_file_path.stem
        steps_file = output_file_path.parent / f"{output_prefix}.steps.md"
        raw_file = output_file_path.parent / f"{output_prefix}.raw.md"
        
        # Initialize files with clean headers
        with open(steps_file, 'w', encoding='utf-8') as f:
            f.write(f"# {team_name.replace('_', ' ')} - Conversation Steps\n\n")
            f.write(f"*Job ID: {job_id}*\n")
            f.write(f"*Timestamp: {datetime.now().isoformat()}*\n\n")
            
            # Add configuration information
            f.write("## Team Configuration\n\n")
            f.write(f"- **Model**: {team_config.get('model', 'N/A')}\n")
            f.write(f"- **Temperature**: {team_config.get('temperature', 'N/A')}\n")
            f.write(f"- **Max Messages**: {team_config.get('max_messages', 'N/A')}\n")
            f.write(f"- **Allow Repeated Speaker**: {team_config.get('allow_repeated_speaker', 'N/A')}\n")
            f.write(f"- **Max Selector Attempts**: {team_config.get('max_selector_attempts', 'N/A')}\n")
            f.write(f"- **Termination Keyword**: {team_config.get('termination_keyword', 'N/A')}\n\n")
        with open(raw_file, 'w', encoding='utf-8') as f:
            f.write(f"# {team_name.replace('_', ' ')} - Raw Debug Data\n\n")
            f.write(f"Job ID: {job_id}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
        
        # Run the team and write output in real-time
        final_markdown_content = None
        print(f"Starting {team_name} execution...")
        
        async for message in team.run_stream(task=task_message):
            # Check for cancellation
            if cancellation_flag and cancellation_flag.is_set():
                print(f"⚠️ Team {team_name} cancelled during execution")
                return False
            
            # Always save raw message for debugging
            raw_content = f"**Raw Message**: {str(message)}\n\n"
            with open(raw_file, 'a', encoding='utf-8') as raw_f:
                raw_f.write(raw_content)
            
            # Extract clean content and process
            clean_content, source_name = self._extract_message_content(message)
            
            if clean_content:
                # Write clean readable content immediately
                content = f"<!--- SECTION: {source_name.upper().replace('_', ' ')} --->\n{clean_content}\n<!--- END SECTION: {source_name.upper().replace('_', ' ')} --->\n\n"
                with open(steps_file, 'a', encoding='utf-8') as steps_f:
                    steps_f.write(content)
                print(f"[{source_name}]: {clean_content[:100]}...")
                
                # Check if this is the markdown agent's final output
                if source_name == 'markdown_agent':
                    final_markdown_content = self._process_markdown_output(clean_content)
        
        # Save final output
        await self._save_final_output(output_file_path, steps_file, final_markdown_content, 
                                    brief_content, team_name)
        
        print(f"✓ {team_name} execution completed")
        return True
    
    def _extract_message_content(self, message):
        """Extract clean content from various message types."""
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
        
        # Handle case where clean_content might be a list
        if isinstance(clean_content, list):
            if clean_content and isinstance(clean_content[0], str):
                clean_content = clean_content[0]
            else:
                clean_content = str(clean_content)
        
        return clean_content, source_name
    
    def _process_markdown_output(self, content: str) -> str:
        """Process markdown agent output to extract clean content."""
        content = content.strip()
        
        # Remove markdown code block wrappers if present
        if content.startswith('```markdown') or content.startswith('```'):
            lines = content.split('\n')
            content_lines = []
            in_content = False
            
            for line in lines:
                if line.strip() in ['```markdown', '```'] and not in_content:
                    in_content = True
                    continue
                elif line.strip() in ['```', 'TERMINATE']:
                    break
                elif in_content:
                    content_lines.append(line)
            
            return '\n'.join(content_lines).strip()
        else:
            # Remove any trailing TERMINATE and workflow completion messages
            final_content = content.replace('TERMINATE', '').strip()
            
            # Remove workflow completion messages
            lines = final_content.split('\n')
            cleaned_lines = []
            for line in lines:
                if 'workflow complete' not in line.lower() and 'ready for' not in line.lower():
                    cleaned_lines.append(line)
            return '\n'.join(cleaned_lines).strip()
    
    async def _save_final_output(self, output_file_path: Path, steps_file: Path, 
                               final_markdown_content: str, brief_content: str, team_name: str):
        """Save the final output to the designated file."""
        
        if final_markdown_content:
            # Append content brief to the final markdown content if available and in planning phase
            if brief_content and 'Planning' in team_name:
                final_markdown_content += f"\n\n<!--- SECTION: CONTENT BRIEF --->\n\n{brief_content}\n<!--- END SECTION: CONTENT BRIEF  --->"
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(final_markdown_content)
            print(f"✓ {team_name} final output saved to: {output_file_path}")
        else:
            # Fallback: read the clean conversation steps file
            with open(steps_file, 'r', encoding='utf-8') as steps_f:
                clean_output = steps_f.read()
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(clean_output)
            print(f"✓ {team_name} execution completed (fallback output)")
    
    async def _create_error_output(self, output_file_path: Path, team_name: str, job_id: str, 
                                 yaml_config_path: Path, error_msg: str, traceback_str: str):
        """Create error output file when team execution fails."""
        
        error_content = f"""# {team_name} - Execution Error

An error occurred while running {team_name}:

**Error**: {error_msg}
**Timestamp**: {datetime.now().isoformat()}
**Configuration**: {yaml_config_path}

## Troubleshooting

1. Check that the YAML configuration file is valid
2. Verify all required dependencies are installed
3. Ensure input data is properly formatted
4. Review the error message above for specific details

## Full Error Details
{traceback_str}
"""
        
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(error_content)
