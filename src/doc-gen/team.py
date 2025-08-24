#!/usr/bin/env python3
"""
Team

Represents a workflow team with complete configuration.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from observable import ObservableStore


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


class Team:
    """Represents a workflow team with its configuration"""
    
    def __init__(self, config: TeamConfig):
        """Initialize team with complete configuration"""
        self.config = config
        self.observable = None
    
    def initialize(self, observable: ObservableStore):
        """Initialize team with observable store and subscribe to status changes"""
        self.observable = observable
        # Register team subscription using the team's declared dependency (if any).
        # `depends_on` is a team id this team depends on; register that so the
        # observable can trigger this team's start/stop when the dependency updates.
        try:
            # Always register the team with the observable. If the team has no
            # declared dependency (`depends_on`), pass an empty list. The
            # ObservableStore treats an empty dependency list as an immediate
            # trigger for the default "ready" action so teams with no
            # dependencies run in parallel.
            agent_deps = [self.depends_on] if self.depends_on else []
            self._unsubscribe = self.observable.subscribe_team(self, agent_deps)
        except Exception:
            # If observable doesn't support team subscriptions, ignore silently
            self._unsubscribe = None
        print(f"Team '{self.id}' (template: {self.template}) registered with observable store")

    def start(self, agent_ids: List[str]):
        """Start the team's agents based on the provided dependent agent IDs.

        This method is intended to be long-running and idempotent: calling it
        multiple times should not create duplicate agents. Teams should update
        the observable with agent status changes as agents run.
        """
        # Minimal idempotent scaffold - real implementation should create agents
        print(f"Team '{self.id}': start called for agents {agent_ids}")

    def stop(self, force: bool = False):
        """Stop all running agents for this team. If force is True, kill processes."""
        print(f"Team '{self.id}': stop called (force={force})")
    
    def _on_status_change(self, data: Dict[str, Any]):
        """Handle status changes from the observable store"""
        # Teams can react to status changes here
        if 'team_status' in data and self.id in data['team_status']:
            team_status = data['team_status'][self.id]
            print(f"Team '{self.id}' status changed to: {team_status}")
    
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
    def depends_on(self) -> Optional[str]:
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
