"""Team runner abstractions.

This small module provides a very light abstraction layer so each Team can be
bound to a runner object that encapsulates agent setup / execution / teardown.

Making this a separate module with explicit exports and type hints helps the
editor (e.g. VS Code) surface auto-import (quick fix) suggestions for the two
public symbols: TeamRunner and TeamRunnerFactory.
"""

from __future__ import annotations
from typing import Optional, Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from team import TeamConfig

__all__ = ["TeamRunner", "TeamRunnerFactory"]


class Logger(Protocol):
    """Logger protocol for type hints."""
    def log(self, message: str, component: str = "core") -> None: ...
    def error(self, message: str, component: str = "core") -> None: ...


class TeamRunner:
    """Executes a team's logic (placeholder implementation)."""

    def __init__(self, team_config: Optional[TeamConfig] = None, logger: Optional[Logger] = None, vector_memory=None):
        self.team_config = team_config  # complete team configuration
        self.logger = logger
        self.vector_memory = vector_memory  # vector database for retrieval
        self._initialized = False
        self._running = False

    def initialize(self) -> None:
        """Set up any agents/resources required for this team.

        In a future implementation you can populate self.agents, load tools, etc.
        """
        if self.logger and self.team_config:
            self.logger.log(f"Initializing team runner for team {self.team_config.id}", "team_runner")
            self.logger.log(f"Team config: model={self.team_config.model}, max_messages={self.team_config.max_messages}", "team_runner")
            if self.vector_memory:
                self.logger.log(f"Vector memory available for team {self.team_config.id}", "team_runner")
            else:
                self.logger.log(f"No vector memory available for team {self.team_config.id}", "team_runner")
        elif self.logger:
            self.logger.log("Initializing team runner (no config provided)", "team_runner")
        self._initialized = True

    def run(self) -> None:
        """Execute the team's conversation / workflow."""
        if not self._initialized:
            # Lazy initialize if user forgot.
            self.initialize()
        
        team_id = self.team_config.id if self.team_config else '<unknown>'
        if self.logger:
            self.logger.log(f"Running team {team_id}", "team_runner")
            if self.vector_memory:
                self.logger.log(f"Team {team_id} has access to vector memory for retrieval", "team_runner")
        
        self._running = True
        # Placeholder: real logic would stream messages, etc.
        # Here's where you'd use self.team_config.model, self.team_config.temperature, etc.
        # And where you'd use self.vector_memory for document retrieval

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