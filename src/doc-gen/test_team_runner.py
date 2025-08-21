"""Test-specific team runner for simulating various scenarios.

This runner uses the test_* properties in TeamConfig to simulate:
- Delays and timeouts
- Failures and exceptions  
- Partial completions
- Progress updates
- Flaky behavior
"""

import time
import random
from typing import Optional, TYPE_CHECKING
from team_runner import TeamRunner

if TYPE_CHECKING:
    from team import TeamConfig
    from logger import Logger


class MockTeamRunner(TeamRunner):
    """Enhanced team runner for testing scenarios."""
    
    def __init__(self, team_config: Optional['TeamConfig'] = None, logger: Optional['Logger'] = None):
        super().__init__(team_config, logger)
        self._progress_count = 0
    
    def run(self) -> None:
        """Execute the team with test behaviors based on config."""
        if not self._initialized:
            self.initialize()
        
        team_id = self.team_config.id if self.team_config else '<unknown>'
        if self.logger:
            self.logger.log(f"Starting test run for team {team_id}", "test_team_runner")
        
        self._running = True
        
        if not self.team_config:
            # No config, just do basic run
            super().run()
            return
        
        try:
            # Check for success probability (flaky behavior)
            if self.team_config.test_success_probability is not None:
                if random.random() > self.team_config.test_success_probability:
                    self._simulate_failure("Random failure (flaky test)")
                    return
            
            # Check for immediate failure mode (no delay specified)
            if (self.team_config.test_failure_mode is not None and 
                self.team_config.test_failure_delay is None):
                # Generate partial output if configured
                if self.team_config.test_partial_output:
                    if self.logger:
                        self.logger.log(f"Team {team_id}: Generated partial output before failure", "test_team_runner")
                
                self._simulate_failure()
                return
            
            # Simulate progress steps
            total_steps = self.team_config.test_progress_steps or 1
            delay_per_step = (self.team_config.test_delay_seconds or 0) / total_steps
            
            for step in range(total_steps):
                self._progress_count = step + 1
                
                if self.logger:
                    self.logger.log(f"Team {team_id}: Progress {self._progress_count}/{total_steps}", "test_team_runner")
                
                # Check if we should fail at this step
                if (self.team_config.test_failure_delay is not None and 
                    step * delay_per_step >= self.team_config.test_failure_delay):
                    
                    # Generate partial output if configured
                    if self.team_config.test_partial_output:
                        if self.logger:
                            self.logger.log(f"Team {team_id}: Generated partial output before failure", "test_team_runner")
                    
                    self._simulate_failure()
                    return
                
                # Wait for this step
                if delay_per_step > 0:
                    time.sleep(delay_per_step)
            
            # Successful completion
            if self.logger:
                self.logger.log(f"Team {team_id}: Completed successfully", "test_team_runner")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Team {team_id}: Unexpected error - {str(e)}", "test_team_runner")
            raise
        finally:
            self._running = False
    
    def _simulate_failure(self, custom_message: Optional[str] = None):
        """Simulate different types of failures based on config."""
        team_id = self.team_config.id if self.team_config else '<unknown>'
        failure_mode = self.team_config.test_failure_mode if self.team_config else None
        
        message = custom_message or self.team_config.test_failure_message or "Test failure"
        
        if failure_mode == "exception":
            if self.logger:
                self.logger.error(f"Team {team_id}: Raising exception - {message}", "test_team_runner")
            raise RuntimeError(f"Test exception for team {team_id}: {message}")
        
        elif failure_mode == "timeout":
            if self.logger:
                self.logger.error(f"Team {team_id}: Simulating timeout - {message}", "test_team_runner")
            # In real scenario, this would be a timeout, but we'll just log it
            
        elif failure_mode == "partial_failure":
            if self.logger:
                self.logger.error(f"Team {team_id}: Partial failure - {message}", "test_team_runner")
                self.logger.log(f"Team {team_id}: Some work completed before failure", "test_team_runner")
        
        else:
            # Generic failure
            if self.logger:
                self.logger.error(f"Team {team_id}: Failed - {message}", "test_team_runner")
    
    def get_progress(self) -> dict:
        """Get current progress information."""
        total_steps = self.team_config.test_progress_steps or 1 if self.team_config else 1
        return {
            "team_id": self.team_config.id if self.team_config else '<unknown>',
            "current_step": self._progress_count,
            "total_steps": total_steps,
            "percentage": (self._progress_count / total_steps) * 100,
            "running": self._running
        }


class MockTeamRunnerFactory:
    """Factory for creating test team runners."""
    
    def __init__(self, logger_factory: Optional[any] = None):
        self.logger_factory = logger_factory
    
    def create(self, team: any) -> MockTeamRunner:
        logger = None
        if self.logger_factory:
            logger = self.logger_factory.create_logger("test_team_runner")
        
        team_config = getattr(team, 'config', None)
        return MockTeamRunner(team_config, logger)
