"""Database connection management with retry logic.

Handles SQLite connections with optimal pragmas for concurrent access,
WAL mode for write concurrency, and automatic retry on lock timeouts.
"""

import sqlite3
import time
import functools
from pathlib import Path
from typing import Optional, Callable, Any, TypeVar
from contextlib import contextmanager

DEFAULT_DB_PATH = Path.home() / ".cache" / "ast-tools" / "codebase.db"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 0.5  # seconds
BACKOFF_MULTIPLIER = 2.0

F = TypeVar("F", bound=Callable[..., Any])


def retry_on_locked(max_attempts: int = MAX_RETRIES, initial_delay: float = RETRY_DELAY) -> Callable[[F], F]:
    """Decorator to retry database operations on "database is locked" errors.
    
    Uses exponential backoff: delay = initial_delay * (backoff_multiplier ^ attempt)
    
    Args:
        max_attempts: Maximum retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 0.5)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_on_locked(max_attempts=5, initial_delay=0.2)
        def insert_symbol(conn, symbol):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" not in str(e).lower():
                        raise  # Not a lock error, re-raise immediately
                    
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        delay *= BACKOFF_MULTIPLIER
            
            # All retries exhausted
            raise sqlite3.OperationalError(
                f"Database locked after {max_attempts} retries: {last_exception}"
            ) from last_exception
        
        return wrapper  # type: ignore
    return decorator


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create a SQLite connection with optimal pragmas.
    
    Configures:
        - WAL mode for concurrent reads/writes
        - 64MB cache size
        - 5 second busy timeout
        - NORMAL synchronous mode (balance of safety/speed)
    
    Args:
        db_path: Custom database path (default: ~/.cache/ast-tools/codebase.db)
    
    Returns:
        Configured sqlite3.Connection with row_factory=sqlite3.Row
    
    Note:
        The connection is safe for use in multiple threads with WAL mode enabled.
        However, individual queries should be wrapped in transactions for atomicity.
    """
    db_path = db_path or DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Critical pragmas for performance and concurrency
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA busy_timeout = 5000")  # 5s timeout for locks
    conn.execute("PRAGMA foreign_keys = ON")
    
    return conn


@contextmanager
def database_context(db_path: Optional[Path] = None):
    """Context manager for database connections with automatic cleanup.
    
    Usage:
        with database_context() as conn:
            conn.execute("SELECT * FROM symbols")
    
    Args:
        db_path: Custom database path (default: ~/.cache/ast-tools/codebase.db)
    
    Yields:
        Configured sqlite3.Connection
    
    Note:
        Does NOT automatically commit transactions. Call conn.commit() explicitly
        or wrap in a transaction context for atomic operations.
    """
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_cache_path() -> Path:
    """Get the cache directory path for AST storage.
    
    Returns:
        Path to ~/.cache/ast-tools/ast-cache/
    """
    return Path.home() / ".cache" / "ast-tools" / "ast-cache"


def get_db_path() -> Path:
    """Get the database file path.
    
    Returns:
        Path to ~/.cache/ast-tools/codebase.db
    """
    return DEFAULT_DB_PATH