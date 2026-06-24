"""Secret sanitizer for audit logging.

Redacts sensitive data before storing in audit_log:
- API keys (patterns: *key*, *token*, *secret*, *password*)
- Connection strings (database URLs with credentials)
- File paths containing .env, credentials, secrets
- High-entropy strings (likely secrets)

Usage:
    sanitizer = SecretSanitizer()
    safe_data = sanitizer.sanitize({"api_key": "sk-123", "action": "query"})
"""

import re
import logging
import sqlite3
from typing import Any, Dict, List, Union
from collections.abc import Mapping, Sequence
import math

logger = logging.getLogger(__name__)


class SecretSanitizer:
    """Sanitize sensitive data for audit logging.
    
    Detects and redacts:
    - Known secret patterns (keys, tokens, passwords)
    - Connection strings with credentials
    - High-entropy strings (likely API keys)
    - Common secret file paths
    
    Configurable redaction string and pattern list.
    """
    
    DEFAULT_REDACTION = "***REDACTED***"
    
    # Patterns that suggest sensitive data
    SENSITIVE_PATTERNS = [
        r'(?i)api[_-]?key',
        r'(?i)secret[_-]?key',
        r'(?i)access[_-]?token',
        r'(?i)refresh[_-]?token',
        r'(?i)auth[_-]?token',
        r'(?i)bearer[_-]?token',
        r'(?i)token',  # Standalone token (catches nested "token" keys)
        r'(?i)private[_-]?key',
        r'(?i)password',
        r'(?i)passwd',
        r'(?i)credential',
        r'(?i)connection[_-]?string',
        r'(?i)database[_-]?url',
        r'(?i)db[_-]?password',
        r'(?i)db[_-]?user',
    ]
    
    # File paths that likely contain secrets
    SENSITIVE_PATHS = [
        '.env',
        '.env.local',
        '.env.production',
        'credentials',
        'secrets',
        'id_rsa',
        'id_ed25519',
        '.ssh/',
        '.gnupg/',
        'keystore',
        '.pem',
        '.key',
        '.p12',
        '.pfx',
    ]
    
    def __init__(self, redaction: str = None, extra_patterns: List[str] = None):
        """Initialize sanitizer.
        
        Args:
            redaction: Replacement string for redacted values
            extra_patterns: Additional regex patterns to detect
        """
        self.redaction = redaction or self.DEFAULT_REDACTION
        self.patterns = self.SENSITIVE_PATTERNS + (extra_patterns or [])
        self._compiled_patterns = [re.compile(p) for p in self.patterns]
    
    def sanitize(self, data: Any) -> Any:
        """Sanitize data recursively.
        
        Handles:
        - Dicts: sanitize keys and values
        - Lists/tuples: sanitize each item
        - Strings: check for patterns and entropy
        - Other: return as-is
        
        Args:
            data: Data to sanitize
        
        Returns:
            Sanitized data with same structure
        """
        if isinstance(data, Mapping):
            result = {}
            for k, v in data.items():
                # First check if key suggests sensitive data
                if isinstance(k, str):
                    safe_v = self._sanitize_value(k, v)
                else:
                    safe_v = v
                # Then recursively sanitize the value
                result[k] = self.sanitize(safe_v)
            return result
        elif isinstance(data, Sequence) and not isinstance(data, str):
            return [self.sanitize(item) for item in data]
        elif isinstance(data, str):
            return self._sanitize_string(data)
        else:
            return data
    
    def _sanitize_string(self, value: str) -> str:
        """Sanitize a string value.
        
        Checks:
        1. Key name matches sensitive patterns
        2. Value looks like a secret (high entropy)
        3. Value is a path to sensitive file
        
        Args:
            value: String to sanitize
        
        Returns:
            Redacted string or original
        """
        # Check if it looks like a path to sensitive file
        for sensitive_path in self.SENSITIVE_PATHS:
            if sensitive_path in value:
                logger.debug(f"Redacted sensitive path: {value[:50]}")
                return self.redaction
        
        # Check entropy (API keys tend to be high entropy)
        if self._is_high_entropy(value) and len(value) >= 20:
            # But allow normal text
            if not self._is_likely_text(value):
                logger.debug(f"Redacted high-entropy string: {value[:20]}...")
                return self.redaction
        
        return value
    
    def _sanitize_value(self, key: str, value: Any) -> Any:
        """Sanitize a key-value pair.
        
        Args:
            key: Key name (used for pattern matching)
            value: Value to sanitize
        
        Returns:
            Sanitized value
        """
        if not isinstance(key, str):
            return value
        
        # Check if key matches sensitive patterns
        key_lower = key.lower()
        for pattern in self._compiled_patterns:
            if pattern.search(key_lower):
                logger.debug(f"Redacted sensitive key: {key}")
                return self.redaction
        
        # If value is string, apply string sanitization
        if isinstance(value, str):
            return self._sanitize_string(value)
        
        return value
    
    def _is_high_entropy(self, text: str) -> bool:
        """Check if text has high entropy (likely a secret).
        
        Uses Shannon entropy calculation.
        Threshold: > 4.0 bits/char suggests randomness.
        
        Args:
            text: Text to analyze
        
        Returns:
            True if high entropy
        """
        if len(text) < 8:
            return False
        
        # Count character frequencies
        freq = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1
        
        # Calculate entropy
        entropy = 0.0
        length = len(text)
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        
        # API keys typically have entropy > 4.0
        return entropy > 4.0
    
    def _is_likely_text(self, text: str) -> bool:
        """Check if text is likely natural language.
        
        Heuristics:
        - Contains spaces (words)
        - Has mixed case but not all caps
        - Contains common letters
      
        Args:
            text: Text to analyze
        
        Returns:
            True if likely natural text
        """
        # Contains spaces = likely text
        if ' ' in text and len(text.split()) > 2:
            return True
        
        # Has typical word patterns
        if re.search(r'[aeiou]{2,}', text, re.IGNORECASE):
            return True
        
        # Mostly lowercase with some uppercase (normal text)
        upper_ratio = sum(1 for c in text if c.isupper()) / len(text)
        if 0.05 < upper_ratio < 0.3:
            return True
      
        return False


def sanitize_for_audit(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for audit log sanitization.
    
    Usage:
        safe_data = sanitize_for_audit({"api_key": "sk-...", "query": "SELECT ..."})
    
    Args:
        data: Data to sanitize
    
    Returns:
        Sanitized data safe for audit logging
    """
    sanitizer = SecretSanitizer()
    return sanitizer.sanitize(data)


def log_audit_event(
    conn: sqlite3.Connection,
    user: str,
    action: str,
    resource: str,
    details: Dict[str, Any],
    result: str = "success"
) -> int:
    """Log an audit event with automatic sanitization.
    
    Usage:
        log_audit_event(conn, "user123", "query", "symbols", {"q": "test"})
    
    Args:
        conn: SQLite connection
        user: User identifier
        action: Action performed
        resource: Resource accessed
        details: Additional details (will be sanitized)
        result: Result status
    
    Returns:
        Row ID of inserted audit log entry
    """
    import json
    from datetime import datetime
    
    # Sanitize details
    safe_details = sanitize_for_audit(details)
    
    cursor = conn.execute("""
        INSERT INTO audit_log 
        (timestamp, user_id, action, target_id, ip_address, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        int(datetime.now().timestamp()),
        user,
        action,
        resource,
        None,  # ip_address
        json.dumps(safe_details)
    ))
    
    row_id = cursor.lastrowid
    logger.debug(f"Audit log entry {row_id}: {user} {action} {resource}")
    
    return row_id