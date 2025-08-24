"""Team runner abstractions.

This small module provides a very light abstraction layer so each Team can be
bound to a runner object that encapsulates agent setup / execution / teardown.

Making this a separate module with explicit exports and type hints helps the
editor (e.g. VS Code) surface auto-import (quick fix) suggestions for the two
public symbols: TeamRunner and TeamRunnerFactory.
"""

from __future__ import annotations
from typing import Optional, Any

__all__ = ["TeamRunner", "TeamRunnerFactory"]


class TeamRunner:
    """Executes a team's logic (placeholder implementation)."""

    def __init__(self, team: Optional[Any] = None):
        self.team = team  # stored for future use (logging, access to config, etc.)
        self._initialized = False
        self._running = False

    def initialize(self) -> None:
        """Set up any agents/resources required for this team.

        In a future implementation you can populate self.agents, load tools, etc.
        """
        self._initialized = True

    def run(self) -> None:
        """Execute the team's conversation / workflow."""
        if not self._initialized:
            # Lazy initialize if user forgot.
            self.initialize()
        self._running = True
        # Placeholder: real logic would stream messages, etc.
        # print(f"Running team {getattr(self.team, 'id', '<unknown>')}")

    def stop(self, force: bool = False) -> None:
        """Stop execution and release resources."""
        if self._running:
            # Placeholder for cleanup logic
            self._running = False


class TeamRunnerFactory:
    """Factory responsible for constructing TeamRunner instances.

    Kept as a class (instead of a bare function) so that future dependency
    injection (e.g. passing shared model clients, caches) is straightforward.
    """

    def create(self, team: Any) -> TeamRunner:
        return TeamRunner(team)