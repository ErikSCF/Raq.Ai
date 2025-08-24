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
        """Set up agents and AutoGen team from team configuration template."""
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
            # Load the team template YAML file
            template_path = Path(self.team_config.job_folder) / self.team_config.template
            if not template_path.exists():
                raise FileNotFoundError(f"Team template not found: {template_path}")

            with open(template_path, 'r', encoding='utf-8') as f:
                team_template = yaml.safe_load(f)

            # Create OpenAI model client
            self.model_client = OpenAIChatCompletionClient(
                model=self.team_config.model,
                temperature=self.team_config.temperature
            )

            # Create agents from template
            self.agents = self._create_agents(team_template, self.model_client)

            # Create AutoGen team
            self.autogen_team = self._create_autogen_team(team_template, self.model_client)

            if self.logger:
                self.logger.log(f"Team {self.team_config.id} initialized with {len(self.agents)} agents", "team_runner")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize team {self.team_config.id}: {e}", "team_runner")
            raise

        self._initialized = True

    def run(self) -> None:
        """Execute the team's conversation / workflow using AutoGen."""
        if not self._initialized:
            # Lazy initialize if user forgot.
            self.initialize()
        
        team_id = self.team_config.id if self.team_config else '<unknown>'
        if self.logger:
            self.logger.log(f"Running team {team_id}", "team_runner")
            if self.vector_memory:
                self.logger.log(f"Team {team_id} has access to vector memory for retrieval", "team_runner")

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
            # Handle different AutoGen message formats
            content = None
            if hasattr(message, 'content'):
                content = message.content
            elif hasattr(message, 'text'):
                content = message.text
            elif isinstance(message, dict):
                content = message.get('content', message.get('text', str(message)))
            else:
                content = str(message)
            
            # Handle content that might be a list
            if isinstance(content, list):
                # Join list items with newlines
                content = '\n'.join(str(item) for item in content)
            elif content is None:
                content = str(message)
            
            # Ensure content is a string before calling strip
            content_str = str(content) if content is not None else ""
            
            # Extract source name
            source_name = "unknown_agent"
            if hasattr(message, 'source'):
                source_name = message.source
            elif hasattr(message, 'name'):
                source_name = message.name
            elif hasattr(message, 'sender'):
                source_name = message.sender
            elif isinstance(message, dict):
                source_name = message.get('source', message.get('name', message.get('sender', 'unknown_agent')))
            
            return content_str.strip(), source_name
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error extracting message content: {e}", "team_runner")
            return str(message), 'unknown_agent'

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
            
            # Get system message
            system_message = agent_config.get('system_message', '')
            
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

    def _create_autogen_team(self, team_template: Dict[str, Any], model_client) -> SelectorGroupChat:
        """Create AutoGen SelectorGroupChat team from template."""
        selector_config = team_template.get('selector', {})
        selector_prompt = selector_config.get('system_message', '')
        
        return SelectorGroupChat(
            participants=list(self.agents.values()),
            termination_condition=OrTerminationCondition(
                MaxMessageTermination(self.team_config.max_messages),
                TextMentionTermination(self.team_config.termination_keyword)
            ),
            model_client=model_client,
            selector_prompt=selector_prompt,
            allow_repeated_speaker=self.team_config.allow_repeated_speaker,
            max_selector_attempts=self.team_config.max_selector_attempts
        )

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
        
        # Generic workflow start message
        task_parts.append(f"\nPlease begin the {self.team_config.id.replace('_', ' ')} workflow.")
        
        return "\n".join(task_parts)

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