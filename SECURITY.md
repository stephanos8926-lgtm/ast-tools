# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

The ast-tools project takes security seriously. If you discover a security
vulnerability, please **do not** open a public issue.

Instead, send a detailed report to:

**Steven Page** — <steven@rapidwebs.io>

We will acknowledge receipt within 48 hours and provide an estimated timeline
for a fix. Security issues will be prioritized above all other work.

### What to include

- Type of vulnerability (e.g., command injection, path traversal, XSS)
- Full path to the affected file(s) and line number(s)
- Steps to reproduce
- Proof of concept (if applicable)
- Impact assessment

### What to expect

- **Initial response**: within 48 hours
- **Fix timeline**: depends on severity
  - CRITICAL: within 72 hours
  - HIGH: within 1 week
  - MEDIUM: within 2 weeks
  - LOW: next release cycle

## Security Features

### Path Traversal Protection

All tools that accept file paths validate them against workspace boundaries.
The `security.py` module provides path validation and injection prevention.

### Secret Sanitization

The `secret_sanitizer.py` module detects and redacts API keys, passwords,
and other sensitive patterns in code analysis output.

### Input Validation

All user-provided inputs are validated before use. File paths are resolved
and checked for existence before operations.

## Known Security Considerations

- **ast-tools parses arbitrary code.** The parser may encounter malicious
  files designed to exploit tree-sitter. We sandbox parsing where possible.
- **Semantic search indexes local code.** Ensure only authorized users have
  access to the index database.
- **MCP server mode accepts external requests.** Run behind a firewall or
  authentication proxy when exposed to a network.

## Responsible Disclosure

We kindly ask that you follow responsible disclosure practices:

1. Notify us privately first
2. Allow time for a fix before public disclosure
3. Coordinate disclosure timing with us

Thank you for helping keep ast-tools and its users safe.
