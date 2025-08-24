#!/usr/bin/env python3
"""Demo of MockTeamRunner with various test scenarios."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from team import TeamConfig
from tests.mock_team_runner import MockTeamRunner, MockTeamRunnerFactory
from logger import MemoryLoggerFactory


def demo_mock_team_runner():
    """Demonstrate various MockTeamRunner scenarios."""
    
    print("🧪 MockTeamRunner Demo - Testing Various Scenarios")
    print("=" * 60)
    
    logger_factory = MemoryLoggerFactory()
    
    # Scenario 1: Successful run with progress steps
    print("\n1️⃣  Successful Run with Progress Steps")
    config1 = TeamConfig(
        id="success_team",
        template="SuccessTemplate.yaml",
        output_file="success_output.md",
        depends_on=None,
        input_files=[],
        step_files=[],
        agent_result=None,
        model="gpt-4o-mini",
        temperature=0.3,
        max_messages=10,
        allow_repeated_speaker=False,
        max_selector_attempts=3,
        termination_keyword="TERMINATE",
        test_delay_seconds=0.1,
        test_progress_steps=3
    )
    
    runner1 = MockTeamRunner(config1, logger_factory.create_logger())
    runner1.run()
    
    print(f"   Progress: {runner1.get_progress()}")
    
    # Scenario 2: Exception failure
    print("\n2️⃣  Exception Failure Mode")
    config2 = TeamConfig(
        id="exception_team",
        template="ExceptionTemplate.yaml", 
        output_file="exception_output.md",
        depends_on=None,
        input_files=[],
        step_files=[],
        agent_result=None,
        model="gpt-4o-mini",
        temperature=0.3,
        max_messages=10,
        allow_repeated_speaker=False,
        max_selector_attempts=3,
        termination_keyword="TERMINATE",
        test_failure_mode="exception",
        test_failure_message="Simulated critical error"
    )
    
    runner2 = MockTeamRunner(config2, logger_factory.create_logger())
    try:
        runner2.run()
    except RuntimeError as e:
        print(f"   Caught expected exception: {e}")
    
    # Scenario 3: Partial failure with output
    print("\n3️⃣  Partial Failure with Output")
    config3 = TeamConfig(
        id="partial_team",
        template="PartialTemplate.yaml",
        output_file="partial_output.md", 
        depends_on=None,
        input_files=[],
        step_files=[],
        agent_result=None,
        model="gpt-4o-mini",
        temperature=0.3,
        max_messages=10,
        allow_repeated_speaker=False,
        max_selector_attempts=3,
        termination_keyword="TERMINATE",
        test_failure_mode="partial_failure",
        test_partial_output=True,
        test_failure_message="Ran out of memory"
    )
    
    runner3 = MockTeamRunner(config3, logger_factory.create_logger())
    runner3.run()
    
    # Scenario 4: Timeout during progress
    print("\n4️⃣  Timeout During Progress")
    config4 = TeamConfig(
        id="timeout_team",
        template="TimeoutTemplate.yaml",
        output_file="timeout_output.md",
        depends_on=None,
        input_files=[],
        step_files=[],
        agent_result=None,
        model="gpt-4o-mini",
        temperature=0.3,
        max_messages=10,
        allow_repeated_speaker=False,
        max_selector_attempts=3,
        termination_keyword="TERMINATE",
        test_delay_seconds=0.1,
        test_progress_steps=5,
        test_failure_delay=0.05,  # Fail halfway through
        test_failure_mode="timeout"
    )
    
    runner4 = MockTeamRunner(config4, logger_factory.create_logger())
    runner4.run()
    
    print(f"   Progress when timed out: {runner4.get_progress()}")
    
    # Show all logged messages
    print("\n📝 All Logged Messages:")
    shared_logger = logger_factory.create_logger()
    entries = shared_logger.entries()
    
    for i, entry in enumerate(entries, 1):
        status = "❌ ERROR" if entry.is_error else "✅ INFO"
        print(f"   {i:2d}. {status} [{entry.component}] {entry.message}")
    
    print(f"\n📊 Summary: {len(entries)} total messages, {sum(1 for e in entries if e.is_error)} errors")


if __name__ == "__main__":
    demo_mock_team_runner()
