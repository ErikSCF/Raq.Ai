#!/usr/bin/env python3
"""
Team

Represents a workflow team with complete configuration.
"""

from typing import Dict, List, Any, Optional, Union
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
    model: str
    temperature: float
    max_messages: int
    allow_repeated_speaker: bool
    max_selector_attempts: int
    termination_keyword: str
    depends_on: Optional[Union[str, List[str]]] = None
    labeled_inputs: Optional[List[List[str]]] = None  # New labeled input format: [["Label", "filename"]]
    
    # Runtime context (added by workflow manager)
    job_folder: Optional[str] = None
    document_type: Optional[str] = None
    
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
        self.orchestrator = None
        self.team_runner = None
        self.logger_factory = logger_factory or get_default_factory()
        self.logger = self.logger_factory.create_logger("team")
    
    def initialize(self, orchestrator: WorkflowOrchestrator, team_runner_factory: TeamRunnerFactory, vector_memory=None):
        """Initialize team with orchestrator and subscribe to status changes"""
        self.orchestrator = orchestrator
        self.vector_memory = vector_memory
        # Register team subscription using the team's declared dependency (if any).
        # `depends_on` is a team id this team depends on; register that so the
        # observable can trigger this team's start/stop when the dependency updates.
        try:
            # Always register the team with the observable. If the team has no
            # declared dependency (`depends_on`), pass an empty list. The
            # ObservableStore treats an empty dependency list as an immediate
            # trigger for the default "ready" action so teams with no
            # dependencies run in parallel.
            
            # Convert depends_on to list format expected by subscribe_team
            if self.depends_on:
                # Handle both string and list dependencies  
                if isinstance(self.depends_on, list):
                    dependencies = self.depends_on
                else:
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
        """Queue this team for execution by setting status to PENDING"""
        if not self.orchestrator:
            raise RuntimeError(f"Team {self.id} not initialized - call initialize() first")
        self.orchestrator.set(self.id, TaskStatus.PENDING)
        self.logger.log(f"Team '{self.id}' queued for execution")

    def start(self, agent_ids: List[str]):
        """Start the team's execution. Called by orchestrator when dependencies are satisfied.

        This method does the actual team work and updates status accordingly.
        """
        if not self.team_runner:
            raise RuntimeError(f"Team {self.id} not initialized properly")
            
        self.logger.log(f"Team '{self.id}' starting execution with agents {agent_ids}")
        
        try:
            # Mark as started
            self.orchestrator.set(self.id, TaskStatus.STARTED)
            
            # Do the actual work
            self.team_runner.start()
            
            # Mark as completed
            self.orchestrator.set(self.id, TaskStatus.COMPLETE)
            self.logger.log(f"Team '{self.id}' completed successfully")
            
        except Exception as e:
            # Mark as error
            self.orchestrator.set(self.id, TaskStatus.ERROR)
            self.logger.error(f"Team '{self.id}' failed: {e}")
            raise

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
    def depends_on(self) -> Optional[Union[str, List[str]]]:
        """Get team dependency"""
        return self.config.depends_on
    
    @property
    def labeled_inputs(self) -> Optional[List[List[str]]]:
        """Get team labeled inputs"""
        return self.config.labeled_inputs
    
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
