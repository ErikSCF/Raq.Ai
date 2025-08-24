#!/usr/bin/env python3
"""
Team

Represents a workflow team with complete configuration.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from workflow_orchestrator import WorkflowOrchestrator, TaskStatus
from team_runner import TeamRunnerFactory
from logger import LoggerFactory, get_default_factory, Logger
from logger import LoggerFactory, get_default_factory, Logger


@dataclass
class TeamConfig:
    """Complete team configuration with all properties"""
    id: str
    template: str
    output_file: str
    depends_on: Optional[str]
    input_files: List[str]
    step_files: List[str]
    agent_result: Optional[str]
    
    # AutoGen configuration
    model: str
    temperature: float
    max_messages: int
    allow_repeated_speaker: bool
    max_selector_attempts: int
    termination_keyword: str
    
    # Test-specific configuration (optional, for testing scenarios)
    test_delay_seconds: Optional[float] = None  # How long to wait during run()
    test_failure_mode: Optional[str] = None     # "exception", "timeout", "partial_failure", None
    test_failure_delay: Optional[float] = None  # When during run() to trigger failure
    test_failure_message: Optional[str] = None  # Custom failure message
    test_success_probability: Optional[float] = None  # 0.0-1.0, chance of success (for flaky tests)
    test_progress_steps: Optional[int] = None   # Number of progress updates to send
    test_partial_output: Optional[bool] = None  # Whether to generate partial output before failing


class Team:
    """Represents a workflow team with its configuration"""
    
    def __init__(self, config: TeamConfig, logger_factory: Optional[LoggerFactory] = None):
        """Initialize team with complete configuration"""
        self.config = config
        self.observable = None
        self.team_runner = None
        self.logger_factory = logger_factory or get_default_factory()
        self.logger = self.logger_factory.create_logger("team")
    
    def initialize(self, orchestrator: WorkflowOrchestrator, team_runner_factory: TeamRunnerFactory):
        """Initialize team with orchestrator and subscribe to status changes"""
        self.orchestrator = orchestrator
        # Register team subscription using the team's declared dependency (if any).
        # `depends_on` is a team id this team depends on; register that so the
        # observable can trigger this team's start/stop when the dependency updates.
        try:
            # Always register the team with the observable. If the team has no
            # declared dependency (`depends_on`), pass an empty list. The
            # ObservableStore treats an empty dependency list as an immediate
            # trigger for the default "ready" action so teams with no
            # dependencies run in parallel.
            
            # Convert depends_on string to list format expected by subscribe_team
            if self.depends_on:
                # Handle comma-separated dependencies
                dependencies = [dep.strip() for dep in self.depends_on.split(',')]
            else:
                dependencies = []
            
            self._unsubscribe = self.orchestrator.subscribe_team(self, dependencies)
            self.team_runner = team_runner_factory.create(self)
            self.team_runner.initialize()
        except Exception as e:
            # Log the exception instead of silently ignoring it
            self.logger.error(f"Failed to initialize team {self.id}: {e}")
            self._unsubscribe = None
        self.logger.log(f"Team '{self.id}' (template: {self.template}) registered with observable store")

    def run(self): 
        self.observable.set(self.config.id, TaskStatus.PENDING)

    def start(self, agent_ids: List[str]):
        """Start the team's agents based on the provided dependent agent IDs.

        This method is intended to be long-running and idempotent: calling it
        multiple times should not create duplicate agents. Teams should update
        the observable with agent status changes as agents run.
        """
        # Minimal idempotent scaffold - real implementation should create agents
        self.logger.log(f"Team '{self.id}': start called for agents {agent_ids}")
        self.team_runner.run()

    def stop(self, force: bool = False):
        """Stop all running agents for this team. If force is True, kill processes."""
        self.logger.log(f"Team '{self.id}': stop called (force={force})")
        self.team_runner.stop(force)
    
    def _on_status_change(self, data: Dict[str, Any]):
        """Handle status changes from the observable store"""
        # Teams can react to status changes here
        if 'team_status' in data and self.id in data['team_status']:
            team_status = data['team_status'][self.id]
            self.logger.log(f"Team '{self.id}' status changed to: {team_status}")
    
    @property
    def id(self) -> str:
        """Get team id"""
        return self.config.id
    
    @property
    def template(self) -> str:
        """Get team template"""
        return self.config.template
    
    @property
    def output_file(self) -> str:
        """Get team output file"""
        return self.config.output_file
    
    @property
    def depends_on(self) -> List[str]:
        """Get team dependency"""
        return self.config.depends_on
    
    @property
    def input_files(self) -> List[str]:
        """Get team input files"""
        return self.config.input_files
    
    @property
    def step_files(self) -> List[str]:
        """Get team step files"""
        return self.config.step_files
    
    @property
    def agent_result(self) -> Optional[str]:
        """Get team agent result"""
        return self.config.agent_result
    
    # AutoGen configuration properties
    @property
    def model(self) -> str:
        """Get AutoGen model"""
        return self.config.model
    
    @property
    def temperature(self) -> float:
        """Get AutoGen temperature"""
        return self.config.temperature
    
    @property
    def max_messages(self) -> int:
        """Get AutoGen max messages"""
        return self.config.max_messages
    
    @property
    def allow_repeated_speaker(self) -> bool:
        """Get AutoGen allow repeated speaker setting"""
        return self.config.allow_repeated_speaker
    
    @property
    def max_selector_attempts(self) -> int:
        """Get AutoGen max selector attempts"""
        return self.config.max_selector_attempts
    
    @property
    def termination_keyword(self) -> str:
        """Get AutoGen termination keyword"""
        return self.config.termination_keyword
    
    def __str__(self) -> str:
        """String representation of the team"""
        return f"Team(id='{self.id}', template='{self.template}', output_file='{self.output_file}', depends_on={self.depends_on})"
    
    def __repr__(self) -> str:
        """Detailed representation of the team"""
        return f"Team(config={self.config})"
