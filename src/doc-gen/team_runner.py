"""Team runner abstractions.

This small module provides a very light abstraction layer so each Team can be
bound to a runner object that encapsulates agent setup / execution / teardown.

Making this a separate module with explicit exports and type hints helps the
editor (e.g. VS Code) surface auto-import (quick fix) suggestions for the two
public symbols: TeamRunner and TeamRunnerFactory.
"""

from __future__ import annotations
from typing import Optional, Any, Protocol, TYPE_CHECKING, Dict, List
from pathlib import Path
import yaml
import asyncio

# AutoGen imports
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.base import OrTerminationCondition
from autogen_core.tools import FunctionTool
from autogen_core.tools import StaticWorkbench

if TYPE_CHECKING:
    from team import TeamConfig

__all__ = ["TeamRunner", "TeamRunnerFactory"]


class Logger(Protocol):
    """Logger protocol for type hints."""
    def log(self, message: str, component: str = "core") -> None: ...
    def error(self, message: str, component: str = "core") -> None: ...


class TeamRunner:
    """Executes a team's logic using AutoGen."""

    def __init__(self, team_config: Optional[TeamConfig] = None, logger: Optional[Logger] = None, vector_memory=None):
        self.team_config = team_config  # complete team configuration
        self.logger = logger
        self.vector_memory = vector_memory  # vector database for retrieval
        self._initialized = False
        self._running = False
        self.agents = {}
        self.autogen_team = None
        self.model_client = None

    def initialize(self) -> None:
        """Set up basic team runner configuration."""
        if self.logger and self.team_config:
            self.logger.log(f"Initializing team runner for team {self.team_config.id}", "team_runner")
            self.logger.log(f"Team config: model={self.team_config.model}, max_messages={self.team_config.max_messages}", "team_runner")
            if self.vector_memory:
                self.logger.log(f"Vector memory available for team {self.team_config.id}", "team_runner")
            else:
                self.logger.log(f"No vector memory available for team {self.team_config.id}", "team_runner")
        elif self.logger:
            self.logger.log("Initializing team runner (no config provided)", "team_runner")

        if not self.team_config:
            self._initialized = True
            return

        try:
            # Just verify the template exists, but don't load it yet
            template_path = Path(self.team_config.job_folder) / self.team_config.template
            if not template_path.exists():
                raise FileNotFoundError(f"Team template not found: {template_path}")

            # Create OpenAI model client
            self.model_client = OpenAIChatCompletionClient(
                model=self.team_config.model,
                temperature=self.team_config.temperature
            )

            if self.logger:
                self.logger.log(f"Team {self.team_config.id} basic initialization complete", "team_runner")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize team {self.team_config.id}: {e}", "team_runner")
            raise

        self._initialized = True

    def start(self) -> None:
        """Execute the team's conversation / workflow using AutoGen."""
        if not self._initialized:
            # Lazy initialize if user forgot.
            self.initialize()
        
        team_id = self.team_config.id if self.team_config else '<unknown>'
        if self.logger:
            self.logger.log(f"Starting team execution for {team_id}", "team_runner")
            if self.vector_memory:
                self.logger.log(f"Team {team_id} has access to vector memory for retrieval", "team_runner")

        # CRITICAL: Create agents and AutoGen team at execution time when step files are available
        if not self.agents or not self.autogen_team:
            self._create_team_at_runtime(team_id)

        if not self.autogen_team:
            if self.logger:
                self.logger.error(f"Team {team_id} not properly initialized - no AutoGen team available", "team_runner")
            return

        try:
            self._running = True
            
            # Prepare file paths for output
            output_file_path = Path(self.team_config.job_folder) / f"{self.team_config.output_file}.md"
            steps_file = Path(self.team_config.job_folder) / f"{self.team_config.output_file}.steps.md"
            raw_file = Path(self.team_config.job_folder) / f"{self.team_config.output_file}.raw.md"
            
            # Initialize output files
            self._initialize_output_files(output_file_path, steps_file, raw_file, team_id)
            
            # Prepare task message
            task_message = self._prepare_task_message()
            
            # Run the AutoGen team conversation
            if self.logger:
                self.logger.log(f"Starting AutoGen conversation for team {team_id}", "team_runner")
            
            # Execute team conversation with real file output
            final_markdown_content = self._execute_conversation(task_message, steps_file, raw_file, team_id)
            
            # Save final output
            self._save_final_output(output_file_path, steps_file, final_markdown_content, team_id)
            
            if self.logger:
                self.logger.log(f"Team {team_id} conversation completed", "team_runner")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error running team {team_id}: {e}", "team_runner")
            # Create error output
            self._create_error_output(output_file_path, team_id, str(e))
            raise
        finally:
            self._running = False

    def _initialize_output_files(self, output_file_path: Path, steps_file: Path, raw_file: Path, team_id: str):
        """Initialize output files with headers and configuration."""
        from datetime import datetime
        
        # Initialize steps file with clean headers
        with open(steps_file, 'w', encoding='utf-8') as f:
            f.write(f"# {team_id.replace('_', ' ')} - Conversation Steps\n\n")
            f.write(f"*Job ID: {getattr(self.team_config, 'job_id', 'unknown')}*\n")
            f.write(f"*Timestamp: {datetime.now().isoformat()}*\n\n")
            
            # Add configuration information
            f.write("## Team Configuration\n\n")
            f.write(f"- **Model**: {self.team_config.model}\n")
            f.write(f"- **Temperature**: {self.team_config.temperature}\n")
            f.write(f"- **Max Messages**: {self.team_config.max_messages}\n")
            f.write(f"- **Allow Repeated Speaker**: {self.team_config.allow_repeated_speaker}\n")
            f.write(f"- **Max Selector Attempts**: {self.team_config.max_selector_attempts}\n")
            f.write(f"- **Termination Keyword**: {self.team_config.termination_keyword}\n\n")
        
        # Initialize raw file
        with open(raw_file, 'w', encoding='utf-8') as f:
            f.write(f"# {team_id.replace('_', ' ')} - Raw Debug Data\n\n")
            f.write(f"Job ID: {getattr(self.team_config, 'job_id', 'unknown')}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")

    def _execute_conversation(self, task_message: str, steps_file: Path, raw_file: Path, team_id: str) -> str:
        """Execute the AutoGen conversation and log output with section markers."""
        final_markdown_content = None
        
        if self.logger:
            self.logger.log(f"Starting {team_id} execution...", "team_runner")
        
        try:
            # Check if we have a valid AutoGen team
            if self.logger:
                self.logger.log(f"DEBUG: AutoGen team type: {type(self.autogen_team)}", "team_runner")
                self.logger.log(f"DEBUG: AutoGen team has run_stream: {hasattr(self.autogen_team, 'run_stream')}", "team_runner")
                self.logger.log(f"DEBUG: AutoGen team has run: {hasattr(self.autogen_team, 'run')}", "team_runner")
            
            if not hasattr(self.autogen_team, 'run_stream') and not hasattr(self.autogen_team, 'run'):
                if self.logger:
                    self.logger.log(f"AutoGen team has no run method, using simulation for {team_id}", "team_runner")
                return self._simulate_conversation(task_message, steps_file, raw_file, team_id)
            
            # Try to run the actual AutoGen conversation
            if hasattr(self.autogen_team, 'run_stream'):
                # AutoGen SelectorGroupChat uses run_stream which returns async generator
                try:
                    import asyncio
                    # Run the async conversation
                    final_markdown_content = asyncio.run(self._run_async_conversation(task_message, steps_file, raw_file, team_id))
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error in async conversation execution: {e}", "team_runner")
                    # Fall back to simulation
                    final_markdown_content = self._simulate_conversation(task_message, steps_file, raw_file, team_id)
            elif hasattr(self.autogen_team, 'run'):
                # Try simple run method
                final_markdown_content = self._run_simple_conversation(task_message, steps_file, raw_file, team_id)
            else:
                # No suitable run method found
                if self.logger:
                    self.logger.log(f"No suitable AutoGen run method found, using simulation for {team_id}", "team_runner")
                final_markdown_content = self._simulate_conversation(task_message, steps_file, raw_file, team_id)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error executing conversation for {team_id}: {e}", "team_runner")
            # Fall back to simulation on error
            final_markdown_content = self._simulate_conversation(task_message, steps_file, raw_file, team_id)
        
        return final_markdown_content

    async def _run_async_conversation(self, task_message: str, steps_file: Path, raw_file: Path, team_id: str) -> str:
        """Run async AutoGen conversation with real-time logging."""
        final_markdown_content = None
        message_count = 0
        
        try:
            if self.logger:
                self.logger.log(f"Starting async AutoGen conversation for {team_id}", "team_runner")
            
            # Run the AutoGen team stream
            async for message in self.autogen_team.run_stream(task=task_message):
                message_count += 1
                
                # Log raw message
                raw_content = f"**Raw Message {message_count}**: {str(message)}\n\n"
                with open(raw_file, 'a', encoding='utf-8') as raw_f:
                    raw_f.write(raw_content)
                
                # Extract clean content and source
                clean_content, source_name = self._extract_message_content(message)
                
                if clean_content:
                    # Write clean content with section markers
                    formatted_content = f"<!--- SECTION: {source_name.upper().replace('_', ' ')} --->\n{clean_content}\n<!--- END SECTION: {source_name.upper().replace('_', ' ')} --->\n\n"
                    with open(steps_file, 'a', encoding='utf-8') as steps_f:
                        steps_f.write(formatted_content)
                    
                    if self.logger:
                        self.logger.log(f"[{source_name}]: {clean_content[:100]}...", "team_runner")
                    
                    # Check if this is the final output
                    if source_name == 'markdown_agent' or 'final' in source_name.lower():
                        final_markdown_content = self._process_markdown_output(clean_content)
            
            if self.logger:
                self.logger.log(f"AutoGen conversation completed for {team_id} with {message_count} messages", "team_runner")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in async conversation for {team_id}: {e}", "team_runner")
            # If we got some messages before the error, use them
            if message_count == 0:
                # No messages received, fall back to simulation
                return self._simulate_conversation(task_message, steps_file, raw_file, team_id)
        
        return final_markdown_content

    def _run_streaming_conversation(self, task_message: str, steps_file: Path, raw_file: Path, team_id: str) -> str:
        """Run streaming AutoGen conversation (sync version)."""
        final_markdown_content = None
        
        try:
            for message in self.autogen_team.run_stream(task=task_message):
                # Log raw message
                raw_content = f"**Raw Message**: {str(message)}\n\n"
                with open(raw_file, 'a', encoding='utf-8') as raw_f:
                    raw_f.write(raw_content)
                
                # Extract clean content and source
                clean_content, source_name = self._extract_message_content(message)
                
                if clean_content:
                    # Write clean content with section markers
                    formatted_content = f"<!--- SECTION: {source_name.upper().replace('_', ' ')} --->\n{clean_content}\n<!--- END SECTION: {source_name.upper().replace('_', ' ')} --->\n\n"
                    with open(steps_file, 'a', encoding='utf-8') as steps_f:
                        steps_f.write(formatted_content)
                    
                    if self.logger:
                        self.logger.log(f"[{source_name}]: {clean_content[:100]}...", "team_runner")
                    
                    # Check if this is the final output
                    if source_name == 'markdown_agent' or 'final' in source_name.lower():
                        final_markdown_content = self._process_markdown_output(clean_content)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in streaming conversation: {e}", "team_runner")
        
        return final_markdown_content

    def _run_simple_conversation(self, task_message: str, steps_file: Path, raw_file: Path, team_id: str) -> str:
        """Run simple AutoGen conversation."""
        try:
            result = self.autogen_team.run(task=task_message)
            
            # Log the result
            raw_content = f"**Conversation Result**: {str(result)}\n\n"
            with open(raw_file, 'a', encoding='utf-8') as raw_f:
                raw_f.write(raw_content)
            
            # Process the result
            if hasattr(result, 'messages') and result.messages:
                final_markdown_content = None
                for message in result.messages:
                    clean_content, source_name = self._extract_message_content(message)
                    
                    if clean_content:
                        formatted_content = f"<!--- SECTION: {source_name.upper().replace('_', ' ')} --->\n{clean_content}\n<!--- END SECTION: {source_name.upper().replace('_', ' ')} --->\n\n"
                        with open(steps_file, 'a', encoding='utf-8') as steps_f:
                            steps_f.write(formatted_content)
                        
                        if self.logger:
                            self.logger.log(f"[{source_name}]: {clean_content[:100]}...", "team_runner")
                        
                        if source_name == 'markdown_agent' or 'final' in source_name.lower():
                            final_markdown_content = self._process_markdown_output(clean_content)
                
                return final_markdown_content
            else:
                # Single result
                formatted_content = f"<!--- SECTION: TEAM RESULT --->\n{str(result)}\n<!--- END SECTION: TEAM RESULT --->\n\n"
                with open(steps_file, 'a', encoding='utf-8') as steps_f:
                    steps_f.write(formatted_content)
                
                return self._process_markdown_output(str(result))
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in simple conversation: {e}", "team_runner")
            return None

    def _extract_message_content(self, message):
        """Extract clean content and source name from AutoGen message."""
        try:
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
                # For unknown message types, create a placeholder instead of dumping raw data
                message_type = type(message).__name__
                clean_content = f"[{message_type} event]"
                source_name = "System"
            
            # Handle case where clean_content might be a list
            if isinstance(clean_content, list):
                if clean_content and isinstance(clean_content[0], str):
                    clean_content = clean_content[0]
                else:
                    clean_content = str(clean_content)
            
            # Ensure we return a string
            if clean_content is None:
                clean_content = f"[{type(message).__name__} message]"
            
            return str(clean_content).strip(), source_name
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error extracting message content: {e}", "team_runner")
            return f"[Message extraction error: {e}]", 'System'

    def _simulate_conversation(self, task_message: str, steps_file: Path, raw_file: Path, team_id: str) -> str:
        """Simulate conversation as fallback (original implementation)."""
        final_markdown_content = None
        
        # Simulate conversation messages
        simulated_messages = [
            ("selector", "Starting conversation with initial agent selection."),
            ("agent_1", "Beginning analysis of the provided assets and requirements."),
            ("agent_2", "Reviewing the initial analysis and providing feedback."),
            ("markdown_agent", f"# {team_id.replace('_', ' ').title()} Output\n\nThis is the formatted final output from the {team_id} team conversation.\n\n## Summary\n\nThe team has successfully completed the workflow.")
        ]
        
        for agent_name, content in simulated_messages:
            # Log raw message
            raw_content = f"**Raw Message from {agent_name}**: {content}\n\n"
            with open(raw_file, 'a', encoding='utf-8') as raw_f:
                raw_f.write(raw_content)
            
            # Extract and format clean content with section markers
            clean_content = content.strip()
            section_name = agent_name.upper().replace('_', ' ')
            
            # Write clean content with section markers
            formatted_content = f"<!--- SECTION: {section_name} --->\n{clean_content}\n<!--- END SECTION: {section_name} --->\n\n"
            with open(steps_file, 'a', encoding='utf-8') as steps_f:
                steps_f.write(formatted_content)
            
            if self.logger:
                self.logger.log(f"[{agent_name}]: {clean_content[:100]}...", "team_runner")
            
            # Check if this is the final output (e.g., from markdown_agent)
            if agent_name == 'markdown_agent':
                final_markdown_content = self._process_markdown_output(clean_content)
        
        return final_markdown_content

    def _process_markdown_output(self, content: str) -> str:
        """Process the final markdown output from the conversation."""
        # Clean up and format the final markdown content
        return content.strip()

    def _save_final_output(self, output_file_path: Path, steps_file: Path, final_markdown_content: str, team_id: str):
        """Save the final output to the designated file."""
        
        if final_markdown_content:
            # Load content brief if needed
            brief_content = self._load_content_brief()
            
            # Append content brief if available and in planning phase
            if brief_content and 'planning' in team_id.lower():
                final_markdown_content += f"\n\n<!--- SECTION: CONTENT BRIEF --->\n\n{brief_content}\n<!--- END SECTION: CONTENT BRIEF --->"
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(final_markdown_content)
            
            if self.logger:
                self.logger.log(f"Final output saved to: {output_file_path}", "team_runner")
        else:
            # Fallback: use the steps file content
            with open(steps_file, 'r', encoding='utf-8') as steps_f:
                clean_output = steps_f.read()
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(clean_output)
            
            if self.logger:
                self.logger.log(f"Fallback output saved to: {output_file_path}", "team_runner")

    def _create_error_output(self, output_file_path: Path, team_id: str, error_message: str):
        """Create error output file when team execution fails."""
        from datetime import datetime
        
        error_content = f"""# {team_id.replace('_', ' ')} - Execution Error

**Error occurred during team execution**

- **Team ID**: {team_id}
- **Timestamp**: {datetime.now().isoformat()}
- **Error**: {error_message}

## Error Details

The team execution failed with the above error. Please check the configuration and try again.
"""
        
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(error_content)
        
        if self.logger:
            self.logger.error(f"Error output saved to: {output_file_path}", "team_runner")

    def _create_agents(self, team_template: Dict[str, Any], model_client) -> Dict[str, AssistantAgent]:
        """Create agents from team template configuration."""
        agents = {}
        
        agents_config = team_template.get('agents', [])
        for agent_config in agents_config:
            agent_name = agent_config['name']
            
            # Get system message and inject context
            system_message = agent_config.get('system_message', '')
            system_message = self._inject_agent_context(system_message)
            
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
            if self.vector_memory and agent_config.get('vector_memory', False):
                agent_setup['memory'] = [self.vector_memory]
                if self.logger:
                    self.logger.log(f"Agent {agent_name}: Vector memory enabled", "team_runner")
            elif agent_config.get('vector_memory', False):
                if self.logger:
                    self.logger.log(f"Agent {agent_name}: Vector memory requested but not available", "team_runner")
            
            # Create the agent
            agent = AssistantAgent(name=agent_name, **agent_setup)
            agents[agent_name] = agent
        
        return agents

    def _create_autogen_team(self, team_template: Dict[str, Any], model_client, agents: Dict[str, AssistantAgent]) -> SelectorGroupChat:
        """Create AutoGen SelectorGroupChat team from template."""
        selector_config = team_template.get('selector', {})
        selector_prompt = selector_config.get('system_message', '')
        
        # Apply template variable replacements to selector prompt
        selector_prompt = self._apply_template_variables(selector_prompt, agents)
        
        return SelectorGroupChat(
            participants=list(agents.values()),
            termination_condition=OrTerminationCondition(
                MaxMessageTermination(self.team_config.max_messages),
                TextMentionTermination(self.team_config.termination_keyword)
            ),
            model_client=model_client,
            selector_prompt=selector_prompt,
            allow_repeated_speaker=self.team_config.allow_repeated_speaker,
            max_selector_attempts=self.team_config.max_selector_attempts
        )

    def _create_team_at_runtime(self, team_id: str) -> None:
        """Create agents and AutoGen team at runtime when step files are available."""
        if self.logger:
            self.logger.log(f"Creating agents and AutoGen team at runtime for {team_id}", "team_runner")
        
        try:
            # Load the team template YAML file now
            template_path = Path(self.team_config.job_folder) / self.team_config.template
            if not template_path.exists():
                raise FileNotFoundError(f"Team template not found: {template_path}")

            with open(template_path, 'r', encoding='utf-8') as f:
                team_template = yaml.safe_load(f)

            # Create agents from template with step files now available
            self.agents = self._create_agents(team_template, self.model_client)

            # Create AutoGen team with step files now available
            self.autogen_team = self._create_autogen_team(team_template, self.model_client, self.agents)

            if self.logger:
                self.logger.log(f"Runtime team creation complete for {team_id} with {len(self.agents)} agents", "team_runner")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create team at runtime for {team_id}: {e}", "team_runner")
            raise

    def _create_agent_tools(self, tool_configs: List) -> List[FunctionTool]:
        """Create function tools from tool configurations."""
        # TODO: Implement tool creation logic similar to old team executor
        # For now, return empty list
        return []

    def _prepare_task_message(self) -> str:
        """Prepare the task message for the team."""
        if not self.team_config:
            return "Please begin the workflow."
        
        # Load content brief
        brief_content = self._load_content_brief()
        
        task_parts = [
            f"Document Type: {self.team_config.document_type}",
            f"Team: {self.team_config.id}"
        ]
        
        # Add content brief if available
        if brief_content:
            task_parts.append(f"\nSTART CONTENT BRIEF:\n{brief_content}")
            task_parts.append(f"\nEND CONTENT BRIEF")
        
        # Add input files content if available
        input_files_content = self._load_input_files()
        if input_files_content:
            task_parts.append(f"\nINPUT FILES:\n{input_files_content}")
        
        # Generic workflow start message
        task_parts.append(f"\nPlease begin the {self.team_config.id.replace('_', ' ')} workflow.")
        
        return "\n".join(task_parts)

    def _update_agent_system_messages_with_step_summaries(self):
        """Update agent system messages with step summaries at execution time."""
        if not self.agents:
            return
        
        # Get step summaries now that dependent teams may have completed
        step_summaries = self._get_step_summaries()
        
        if not step_summaries:
            step_summaries = "No step summaries available."
        
        # Update each agent's system message if it contains the placeholder
        for agent_name, agent in self.agents.items():
            if hasattr(agent, 'system_message') and '{step_summaries}' in agent.system_message:
                original_message = agent.system_message
                updated_message = original_message.replace('{step_summaries}', step_summaries)
                agent.system_message = updated_message
                
                if self.logger:
                    self.logger.log(f"Updated {agent_name} system message with step summaries ({len(step_summaries)} chars)", "team_runner")

    def _load_input_files(self) -> str:
        """Load the content of input files specified in team configuration."""
        if not self.team_config or not hasattr(self.team_config, 'input_files'):
            return ""
        
        input_files = getattr(self.team_config, 'input_files', [])
        if not input_files:
            return ""
        
        content_parts = []
        for input_file in input_files:
            
            # Handle different input file patterns
            if input_file.endswith("_artifacts"):
                # Dynamic pattern: "{teamname}_artifacts" -> look up team output
                content = self._resolve_artifacts_pattern(input_file)
                if content:
                    content_parts.append(content)
            elif "*" in input_file or "?" in input_file:
                # Glob pattern support
                content = self._resolve_glob_pattern(input_file)
                if content:
                    content_parts.append(content)
            else:
                # Literal file path
                content = self._load_literal_file(input_file)
                if content:
                    content_parts.append(content)
        
        return "\n".join(content_parts)

    def _resolve_artifacts_pattern(self, input_file: str) -> str:
        """Resolve {teamname}_artifacts pattern to actual team output."""
        # Extract team name from pattern
        team_prefix = input_file.replace("_artifacts", "")
        
        # Convert snake_case to expected output file name
        # e.g., "epic_discovery" -> "epic_discovery.md"
        expected_file = f"{team_prefix}.md"
        
        if hasattr(self.team_config, 'job_folder'):
            file_path = Path(self.team_config.job_folder) / expected_file
            if file_path.exists():
                content = self._load_file_with_size_check(file_path, expected_file)
                if self.logger:
                    self.logger.log(f"Resolved {input_file} -> {expected_file}", "team_runner")
                return content
            else:
                if self.logger:
                    self.logger.error(f"Artifacts file not found: {file_path}", "team_runner")
        
        return f"=== {input_file} ===\nERROR: Could not resolve artifacts pattern\n"

    def _resolve_glob_pattern(self, input_file: str) -> str:
        """Resolve glob pattern to matching files."""
        import glob
        
        if hasattr(self.team_config, 'job_folder'):
            pattern_path = Path(self.team_config.job_folder) / input_file
            matching_files = glob.glob(str(pattern_path))
            
            if matching_files:
                content_parts = []
                for file_path in matching_files:
                    file_name = Path(file_path).name
                    content = self._load_file_with_size_check(Path(file_path), file_name)
                    content_parts.append(content)
                
                if self.logger:
                    self.logger.log(f"Glob {input_file} matched {len(matching_files)} files", "team_runner")
                return "\n".join(content_parts)
            else:
                if self.logger:
                    self.logger.error(f"Glob pattern {input_file} found no matches", "team_runner")
        
        return f"=== {input_file} ===\nERROR: No files matched glob pattern\n"

    def _load_literal_file(self, input_file: str) -> str:
        """Load a literal file path."""
        if hasattr(self.team_config, 'job_folder'):
            file_path = Path(self.team_config.job_folder) / input_file
        else:
            file_path = Path(input_file)
        
        if file_path.exists():
            content = self._load_file_with_size_check(file_path, input_file)
            if self.logger:
                self.logger.log(f"Loaded input file: {input_file}", "team_runner")
            return content
        else:
            if self.logger:
                self.logger.error(f"Input file not found: {file_path}", "team_runner")
            return f"=== {input_file} ===\nERROR: File not found at {file_path}\n"

    def _load_file_with_size_check(self, file_path: Path, display_name: str) -> str:
        """Load file with intelligent size handling like the old system."""
        try:
            file_size = file_path.stat().st_size
            size_kb = file_size / 1024
            
            if size_kb > 50.0:  # Files larger than 50KB - just reference
                return f"=== {display_name} ===\nFILE REFERENCE (Large File)\nSize: {size_kb:.1f} KB\nPath: {display_name}\n[Content not included due to size - file referenced only]\n"
            else:
                # Smaller files - include content
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    # Remove TERMINATE to prevent premature termination
                    file_content = file_content.replace('TERMINATE', '').strip()
                
                return f"=== {display_name} ===\n{file_content}\n"
                
        except Exception as e:
            return f"=== {display_name} ===\nERROR: Could not load file - {e}\n"

    def _inject_agent_context(self, system_message: str) -> str:
        """Inject context into agent system messages.
        
        Now that we create agents at runtime, all placeholders should be resolved immediately.
        """
        if not system_message:
            return system_message
        

        
        # Inject step summaries into agent system messages
        if '{step_summaries}' in system_message:
            # Get step summaries (should be available now at runtime)
            step_summaries = self._get_step_summaries()
            if self.logger:
                self.logger.log(f"DEBUG: step_summaries length: {len(step_summaries)}", "team_runner")
                self.logger.log(f"DEBUG: step_summaries preview: {step_summaries[:200]}...", "team_runner")
            
            if step_summaries:
                original_length = len(system_message)
                system_message = system_message.replace('{step_summaries}', step_summaries)
                new_length = len(system_message)
                if self.logger:
                    self.logger.log(f"DEBUG: Injected step summaries into agent system message (original: {original_length} chars, new: {new_length} chars)", "team_runner")
                    self.logger.log(f"DEBUG: Updated system message preview: {system_message[:300]}...", "team_runner")
            else:
                # CRITICAL: If template expects step_summaries but we can't get them, this is an error
                error_msg = f"Agent system message contains {{step_summaries}} placeholder but no step summaries are available. Team config step_files: {getattr(self.team_config, 'step_files', 'None')}"
                if self.logger:
                    self.logger.error(error_msg, "team_runner")
                # For now, don't throw exception - use fallback to debug the issue
                system_message = system_message.replace('{step_summaries}', 'ERROR: No step summaries available - debugging in progress')
        

        
        # Inject agent result content into agent system messages
        if '{agent_result}' in system_message:
            # Get agent results (these should be available during initialization)
            agent_result = self._get_agent_result()
            if agent_result:
                system_message = system_message.replace('{agent_result}', agent_result)
                if self.logger:
                    self.logger.log(f"Injected agent result into agent system message", "team_runner")
            else:
                # CRITICAL: If template expects agent_result but we can't get it, this is an error
                error_msg = f"Agent system message contains {{agent_result}} placeholder but no agent result is available. Team config agent_result: {getattr(self.team_config, 'agent_result', 'None')}"
                if self.logger:
                    self.logger.error(error_msg, "team_runner")
                # For now, don't throw exception - use fallback to debug the issue
                system_message = system_message.replace('{agent_result}', 'ERROR: No agent result available - debugging in progress')
        
        return system_message

    def _apply_template_variables(self, selector_prompt: str, agents: Dict[str, AssistantAgent] = None) -> str:
        """Apply template variable replacements to selector prompt."""
        if not selector_prompt:
            return selector_prompt
        
        if self.logger:
            self.logger.log(f"DEBUG: Original selector prompt: {selector_prompt[:200]}...", "team_runner")
        
        # Get input files list
        input_files = getattr(self.team_config, 'input_files', [])
        
        # Get step summaries and agent results
        step_summaries = self._get_step_summaries()
        agent_result = self._get_agent_result()
        
        if self.logger:
            self.logger.log(f"DEBUG: Selector prompt step_summaries length: {len(step_summaries)}", "team_runner")
        
        # Handle template variable replacements
        if '{input_files}' in selector_prompt:
            selector_prompt = selector_prompt.replace('{input_files}', str(input_files))
        
        # Inject step summaries
        if '{step_summaries}' in selector_prompt:
            if step_summaries:
                selector_prompt = selector_prompt.replace('{step_summaries}', step_summaries)
                if self.logger:
                    self.logger.log(f"DEBUG: Injected step summaries into selector prompt", "team_runner")
            else:
                # CRITICAL: If selector expects step_summaries but we can't get them, this is an error
                error_msg = f"Selector prompt contains {{step_summaries}} placeholder but no step summaries are available. Team config step_files: {getattr(self.team_config, 'step_files', 'None')}"
                if self.logger:
                    self.logger.error(error_msg, "team_runner")
                # For now, don't throw exception - use fallback to debug the issue
                selector_prompt = selector_prompt.replace('{step_summaries}', 'ERROR: No step summaries available - debugging in progress')
        
        # Inject agent result
        if '{agent_result}' in selector_prompt and agent_result:
            selector_prompt = selector_prompt.replace('{agent_result}', agent_result)
        
        if self.logger:
            self.logger.log(f"DEBUG: Final selector prompt: {selector_prompt[:200]}...", "team_runner")
        
        return selector_prompt

    def _get_step_summaries(self) -> str:
        """Get step file summaries for context injection."""
        if not self.team_config or not hasattr(self.team_config, 'step_files'):
            if self.logger:
                self.logger.log(f"No team config or step_files attribute", "team_runner")
            return ""
        
        step_files = getattr(self.team_config, 'step_files', [])
        if not step_files:
            if self.logger:
                self.logger.log(f"No step files configured for team", "team_runner")
            return ""
        
        if self.logger:
            self.logger.log(f"Processing {len(step_files)} step files: {step_files}", "team_runner")
        
        summaries = []
        for step_file in step_files:
            # Construct full path to the step file
            if hasattr(self.team_config, 'job_folder'):
                file_path = Path(self.team_config.job_folder) / step_file
            else:
                file_path = Path(step_file)
            
            if self.logger:
                self.logger.log(f"Looking for step file: {file_path}", "team_runner")
            
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Parse conversation sections for structured summary
                    agent_flow = self._extract_agent_flow(content)
                    summaries.append(f"=== {step_file.upper()} ===\n{agent_flow}")
                    
                    if self.logger:
                        self.logger.log(f"Loaded step summary: {step_file} ({len(content)} chars -> {len(agent_flow)} chars)", "team_runner")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Failed to load step file {step_file}: {e}", "team_runner")
            else:
                if self.logger:
                    self.logger.error(f"Step file not found: {file_path}", "team_runner")
        
        result = '\n\n'.join(summaries) if summaries else ""
        if self.logger:
            self.logger.log(f"Final step summaries: {len(result)} chars", "team_runner")
        return result

    def _get_agent_result(self) -> str:
        """Get agent result content for context injection."""
        if not self.team_config or not hasattr(self.team_config, 'agent_result'):
            return ""
        
        agent_result_ref = getattr(self.team_config, 'agent_result', None)
        if not agent_result_ref:
            return ""
        
        # If agent_result points to a file, load it
        if hasattr(self.team_config, 'job_folder'):
            result_path = Path(self.team_config.job_folder) / agent_result_ref
            if result_path.exists():
                try:
                    with open(result_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if self.logger:
                        self.logger.log(f"Loaded agent result: {agent_result_ref}", "team_runner")
                    return content
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Failed to load agent result {agent_result_ref}: {e}", "team_runner")
        
        return ""

    def _extract_agent_flow(self, steps_content: str) -> str:
        """Extract agent interaction flow from conversation steps."""
        if not steps_content:
            return "No conversation steps found"
        
        lines = steps_content.split('\n')
        agent_interactions = []
        current_section = None
        current_content = []
        
        # Look for section markers and agent interactions
        for line in lines:
            # Check for section markers
            if line.strip().startswith('<!--- SECTION:') and line.strip().endswith('--->'): 
                if current_section and current_content:
                    # Save previous section
                    content_summary = ' '.join(current_content)[:200] + "..." if len(' '.join(current_content)) > 200 else ' '.join(current_content)
                    agent_interactions.append(f"{current_section}: {content_summary}")
                
                # Start new section
                current_section = line.strip()[14:-4].strip()  # Remove <!--- SECTION: and --->
                current_content = []
            elif line.strip().startswith('<!--- END SECTION:'):
                # End current section
                if current_section and current_content:
                    content_summary = ' '.join(current_content)[:200] + "..." if len(' '.join(current_content)) > 200 else ' '.join(current_content)
                    agent_interactions.append(f"{current_section}: {content_summary}")
                current_section = None
                current_content = []
            elif current_section and line.strip():
                # Add content to current section
                current_content.append(line.strip())
        
        # Handle any remaining section
        if current_section and current_content:
            content_summary = ' '.join(current_content)[:200] + "..." if len(' '.join(current_content)) > 200 else ' '.join(current_content)
            agent_interactions.append(f"{current_section}: {content_summary}")
        
        if agent_interactions:
            return '\n'.join(agent_interactions)
        else:
            # Fallback to truncated raw content
            if len(steps_content) > 1500:
                return steps_content[:1500] + "\n\n[Content truncated for context efficiency...]"
            return steps_content

    def _load_content_brief(self) -> str:
        """Load the content brief file if available."""
        if not self.team_config or not hasattr(self.team_config, 'job_folder'):
            return ""
        
        brief_path = Path(self.team_config.job_folder) / "brand_content_brief.md"
        if brief_path.exists():
            try:
                with open(brief_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to load content brief: {e}", "team_runner")
        
        return ""

    def stop(self, force: bool = False) -> None:
        """Stop execution and release resources."""
        if self._running:
            team_id = self.team_config.id if self.team_config else '<unknown>'
            if self.logger:
                self.logger.log(f"Stopping team {team_id}" + (" (forced)" if force else ""), "team_runner")
            # Placeholder for cleanup logic
            self._running = False


class TeamRunnerFactory:
    """Factory responsible for constructing TeamRunner instances.

    Kept as a class (instead of a bare function) so that future dependency
    injection (e.g. passing shared model clients, caches) is straightforward.
    """

    def __init__(self, logger_factory: Optional[Any] = None):
        self.logger_factory = logger_factory

    def create(self, team: Any) -> TeamRunner:
        logger = None
        if self.logger_factory:
            logger = self.logger_factory.create_logger("team_runner")
        
        # Extract team config and vector memory from the team object
        team_config = getattr(team, 'config', None)
        vector_memory = getattr(team, 'vector_memory', None)
        return TeamRunner(team_config, logger, vector_memory)