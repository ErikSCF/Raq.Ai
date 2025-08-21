"""Simple logger implementations for doc-gen with factory pattern.

Two main implementations:
- ConsoleLogger: Writes directly to console (runtime use)
- MemoryLogger: Aggregates entries in memory for testing

Uses factory pattern for dependency injection and testing flexibility.
The intent is to replace scattered print() calls with structured logging.
"""

from __future__ import annotations

import sys
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class LogEntry:
    ts: datetime
    component: str
    message: str
    is_error: bool = False

    def format(self) -> str:
        level = "ERROR" if self.is_error else "INFO"
        return f"{self.ts.strftime('%H:%M:%S')} | {level:<5} | {self.component} | {self.message}"


class Logger(Protocol):
    """Logger protocol for type hints and testing."""
    
    def log(self, message: str, component: str = "core") -> None: ...
    def error(self, message: str, component: str = "core") -> None: ...


class ConsoleLogger:
    """Logger that writes directly to console."""

    def log(self, message: str, component: str = "core") -> None:
        entry = LogEntry(datetime.now(), component, message, is_error=False)
        print(entry.format(), file=sys.stdout)

    def error(self, message: str, component: str = "core") -> None:
        entry = LogEntry(datetime.now(), component, message, is_error=True)
        print(entry.format(), file=sys.stderr)


class MemoryLogger:
    """Logger that aggregates entries in memory for testing."""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._entries: List[LogEntry] = []

    def log(self, message: str, component: str = "core") -> None:
        entry = LogEntry(datetime.now(), component, message, is_error=False)
        with self._lock:
            self._entries.append(entry)

    def error(self, message: str, component: str = "core") -> None:
        entry = LogEntry(datetime.now(), component, message, is_error=True)
        with self._lock:
            self._entries.append(entry)

    def entries(self) -> List[LogEntry]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def has_errors(self) -> bool:
        with self._lock:
            return any(entry.is_error for entry in self._entries)

    def get_messages(self) -> List[str]:
        with self._lock:
            return [entry.message for entry in self._entries]


class LoggerFactory(ABC):
    """Abstract factory for creating loggers."""
    
    @abstractmethod
    def create_logger(self, component: str = "core") -> Logger:
        """Create a logger instance for the given component."""
        pass


class ConsoleLoggerFactory(LoggerFactory):
    """Factory that creates console loggers."""
    
    def create_logger(self, component: str = "core") -> Logger:
        return ConsoleLogger()


class MemoryLoggerFactory(LoggerFactory):
    """Factory for testing that captures logs in memory."""
    
    def __init__(self):
        self._shared_logger: Optional[MemoryLogger] = None
        self._lock = threading.Lock()

    def create_logger(self, component: str = "core") -> Logger:
        """Return shared test logger instance."""
        with self._lock:
            if self._shared_logger is None:
                self._shared_logger = MemoryLogger()
            return self._shared_logger

    def get_entries(self) -> List[LogEntry]:
        """Helper to get all captured log entries."""
        if self._shared_logger:
            return self._shared_logger.entries()
        return []

    def clear(self) -> None:
        """Helper to clear captured entries."""
        if self._shared_logger:
            self._shared_logger.clear()

    def has_errors(self) -> bool:
        """Helper to check if any errors were logged."""
        if self._shared_logger:
            return self._shared_logger.has_errors()
        return False


# Global default factory instance
_default_factory: Optional[LoggerFactory] = None


def get_default_factory() -> LoggerFactory:
    """Get the global default logger factory."""
    global _default_factory
    if _default_factory is None:
        _default_factory = ConsoleLoggerFactory()
    return _default_factory


def set_default_factory(factory: LoggerFactory) -> None:
    """Set the global default logger factory (useful for testing)."""
    global _default_factory
    _default_factory = factory


def get_logger(component: str = "core") -> Logger:
    """Convenience function to get a logger from the default factory."""
    return get_default_factory().create_logger(component)
