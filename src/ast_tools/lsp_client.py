#!/usr/bin/env python3
"""LSP client for ast-tools — type-aware code intelligence.

Bridges Language Server Protocol (LSP) servers to ast-tools for type-aware queries.
Spawns language servers as subprocesses, communicates via JSON-RPC over stdio.

Supported languages (auto-detected):
- Python: pyright-langserver (pip install pyright)
- Rust: rust-analyzer (cargo install rust-analyzer)
- TypeScript: typescript-language-server (npm i -g typescript-language-server)
- Go: gopls (go install golang.org/x/tools/gopls@latest)
- C/C++: clangd (apt install clangd)
"""

import json
import logging
import subprocess
import threading
from collections import namedtuple
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── JSON-RPC Types ─────────────────────────────────────────────────────

JsonRpcRequest = namedtuple("JsonRpcRequest", ["jsonrpc", "id", "method", "params"])
JsonRpcResponse = namedtuple("JsonRpcResponse", ["jsonrpc", "id", "result", "error"])

# ─── LSP Server Config ──────────────────────────────────────────────────

LSP_SERVERS = {
    "python": {
        "command": ["py right-langserver", "--stdio"],
        "install_hint": "pip install pyright",
        "file_extensions": [".py", ".pyi"],
    },
    "rust": {
        "command": ["rust-analyzer"],
        "install_hint": "cargo install rust-analyzer",
        "file_extensions": [".rs"],
    },
    "typescript": {
        "command": ["typescript-language-server", "--stdio"],
        "install_hint": "npm install -g typescript-language-server typescript",
        "file_extensions": [".ts", ".tsx", ".js", ".jsx"],
    },
    "go": {
        "command": ["gopls"],
        "install_hint": "go install golang.org/x/tools/gopls@latest",
        "file_extensions": [".go"],
    },
    "c": {
        "command": ["clangd"],
        "install_hint": "apt install clangd",
        "file_extensions": [".c", ".h"],
    },
    "cpp": {
        "command": ["clangd"],
        "install_hint": "apt install clangd",
        "file_extensions": [".cpp", ".hpp", ".cc", ".cxx"],
    },
}

# ─── LSP Client ─────────────────────────────────────────────────────────


class LSPClient:
    """LSP client that spawns and manages a language server process."""

    def __init__(self, lang: str, root_path: str):
        self.lang = lang
        self.root_path = Path(root_path).resolve()
        self.config = LSP_SERVERS.get(lang)
        if not self.config:
            raise ValueError(f"Unsupported language: {lang}. Supported: {list(LSP_SERVERS.keys())}")

        self.proc: subprocess.Popen | None = None
        self.request_id = 0
        self.pending = {}
        self.lock = threading.Lock()
        self._response_thread = None
        self._running = False

    def start(self):
        """Spawn the language server process."""
        if self.proc:
            return

        cmd = self.config["command"]
        logger.info(f"Starting {self.lang} LSP server: {' '.join(cmd)}")

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(self.root_path),
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"LSP server not found: {cmd[0]}. Install: {self.config['install_hint']}"
            ) from e

        # Start response reader thread
        self._running = True
        self._response_thread = threading.Thread(target=self._read_responses, daemon=True)
        self._response_thread.start()

        # Initialize LSP session
        self._initialize()

    def stop(self):
        """Shutdown the language server."""
        if not self.proc:
            return

        self._running = False
        self._send_notification("shutdown")
        self._send_notification("exit")
        self.proc.terminate()
        self.proc.wait(timeout=5)
        self.proc = None

    def _send_request(self, method: str, params: dict) -> Any:
        """Send an LSP request and wait for response."""
        if not self.proc:
            self.start()

        with self.lock:
            self.request_id += 1
            req_id = self.request_id

        request = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}

        self.pending[req_id] = threading.Event()
        self._write_json(request)

        # Wait for response (30s timeout)
        if not self.pending[req_id].wait(timeout=30):
            raise TimeoutError(f"LSP request {method} timed out")

        with self.lock:
            response = self.pending.pop(req_id)

        if isinstance(response, Exception):
            raise response

        return response

    def _send_notification(self, method: str, params: dict | None = None):
        """Send an LSP notification (no response expected)."""
        if not self.proc:
            self.start()

        notification = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self._write_json(notification)

    def _write_json(self, data: dict):
        """Write JSON-RPC message to LSP server stdin."""
        content = json.dumps(data)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        self.proc.stdin.write(header + content)
        self.proc.stdin.flush()

    def _read_responses(self):
        """Read LSP server responses in background thread."""
        buffer = ""
        while self._running:
            try:
                chunk = self.proc.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk

                # Process complete messages
                while "\r\n\r\n" in buffer:
                    header, rest = buffer.split("\r\n\r\n", 1)
                    content_length = int(header.split("Content-Length: ")[1])

                    if len(rest) >= content_length:
                        body = rest[:content_length]
                        buffer = rest[content_length:]
                        self._process_response(json.loads(body))
                    else:
                        break
            except Exception as e:
                logger.error(f"LSP read error: {e}")
                break

    def _process_response(self, data: dict):
        """Process an LSP response."""
        if "id" in data:
            # Response to our request
            req_id = data["id"]
            with self.lock:
                if req_id in self.pending:
                    if "error" in data:
                        self.pending[req_id] = Exception(data["error"]["message"])
                    else:
                        self.pending[req_id] = data.get("result")
                    self.pending[req_id].set()
        elif "method" in data:
            # Server notification (e.g., diagnostics)
            logger.debug(f"LSP notification: {data['method']}")

    def _initialize(self):
        """Initialize LSP session."""
        result = self._send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": f"file://{self.root_path}",
                "capabilities": {
                    "textDocument": {
                        "synchronization": {"didSave": True},
                        "definition": {"linkSupport": True},
                        "references": {},
                        "hover": {"contentFormat": ["markdown", "plaintext"]},
                        "completion": {"completionItem": {"snippetSupport": False}},
                    }
                },
            },
        )
        self._send_notification("initialized")
        return result

    # ─── LSP Query Methods ──────────────────────────────────────────────

    def goto_definition(self, file: str, line: int, col: int) -> dict | None:
        """Go to definition of symbol at position."""
        uri = f"file://{Path(file).resolve()}"
        result = self._send_request(
            "textDocument/definition",
            {"textDocument": {"uri": uri}, "position": {"line": line - 1, "character": col}},
        )
        return result

    def find_references(self, file: str, line: int, col: int) -> list[dict]:
        """Find all references to symbol at position."""
        uri = f"file://{Path(file).resolve()}"
        result = self._send_request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line - 1, "character": col},
                "context": {"includeDeclaration": True},
            },
        )
        return result or []

    def hover(self, file: str, line: int, col: int) -> str | None:
        """Get type signature and documentation for symbol at position."""
        uri = f"file://{Path(file).resolve()}"
        result = self._send_request(
            "textDocument/hover",
            {"textDocument": {"uri": uri}, "position": {"line": line - 1, "character": col}},
        )
        if result and "contents" in result:
            contents = result["contents"]
            if isinstance(contents, dict):
                return contents.get("value", "")
            elif isinstance(contents, list):
                return "\n".join(c.get("value", str(c)) for c in contents if isinstance(c, dict))
        return None

    def document_symbols(self, file: str) -> list[dict]:
        """Get all symbols in a file."""
        uri = f"file://{Path(file).resolve()}"
        result = self._send_request("textDocument/documentSymbol", {"textDocument": {"uri": uri}})
        return result or []

    def workspace_symbols(self, query: str) -> list[dict]:
        """Search for symbols across the workspace."""
        result = self._send_request("workspace/symbol", {"query": query})
        return result or []

    def call_hierarchy_incoming(self, file: str, line: int, col: int) -> list[dict]:
        """Find all callers of function/method at position."""
        uri = f"file://{Path(file).resolve()}"
        # First get call hierarchy item
        items = self._send_request(
            "textDocument/prepareCallHierarchy",
            {"textDocument": {"uri": uri}, "position": {"line": line - 1, "character": col}},
        )
        if not items:
            return []

        # Then get incoming calls
        result = self._send_request("callHierarchy/incomingCalls", {"item": items[0]})
        return result or []

    def call_hierarchy_outgoing(self, file: str, line: int, col: int) -> list[dict]:
        """Find all functions/methods called by function at position."""
        uri = f"file://{Path(file).resolve()}"
        items = self._send_request(
            "textDocument/prepareCallHierarchy",
            {"textDocument": {"uri": uri}, "position": {"line": line - 1, "character": col}},
        )
        if not items:
            return []

        result = self._send_request("callHierarchy/outgoingCalls", {"item": items[0]})
        return result or []

    def diagnostics(self, file: str) -> list[dict]:
        """Get compiler errors and warnings for a file."""
        # Diagnostics are pushed by server, return last known
        # This would need state tracking - simplified for now
        return []

    def format_document(self, file: str) -> str:
        """Format a file using the language server's formatter."""
        uri = f"file://{Path(file).resolve()}"
        result = self._send_request(
            "textDocument/formatting",
            {"textDocument": {"uri": uri}, "options": {"tabSize": 4, "insertSpaces": True}},
        )
        # Return edits - caller applies them
        return result or []

    def signature_help(self, file: str, line: int, col: int) -> str | None:
        """Get function signature and parameter docs at call site."""
        uri = f"file://{Path(file).resolve()}"
        result = self._send_request(
            "textDocument/signatureHelp",
            {"textDocument": {"uri": uri}, "position": {"line": line - 1, "character": col}},
        )
        if result and "signatures" in result and result["signatures"]:
            sig = result["signatures"][0]
            return sig.get("label", "")
        return None


# ─── Convenience Functions ─────────────────────────────────────────────


def detect_language(file: str) -> str:
    """Detect language from file extension."""
    ext = Path(file).suffix.lower()
    for lang, config in LSP_SERVERS.items():
        if ext in config["file_extensions"]:
            return lang
    return "python"  # Default


def get_lsp_client(file: str, root: str | None = None) -> LSPClient:
    """Get or create an LSP client for a file."""
    lang = detect_language(file)
    root_path = root or str(Path(file).parent)
    return LSPClient(lang, root_path)


# ─── CLI ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python lsp_client.py <command> <file> [line] [col]")
        print("Commands: definition, references, hover, symbols, call-in, call-out")
        sys.exit(1)

    cmd = sys.argv[1]
    file = sys.argv[2]
    line = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    col = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    client = get_lsp_client(file)
    client.start()

    try:
        if cmd == "definition":
            result = client.goto_definition(file, line, col)
            print(json.dumps(result, indent=2))
        elif cmd == "references":
            result = client.find_references(file, line, col)
            print(json.dumps(result, indent=2))
        elif cmd == "hover":
            result = client.hover(file, line, col)
            print(result)
        elif cmd == "symbols":
            result = client.document_symbols(file)
            print(json.dumps(result, indent=2))
        elif cmd == "call-in":
            result = client.call_hierarchy_incoming(file, line, col)
            print(json.dumps(result, indent=2))
        elif cmd == "call-out":
            result = client.call_hierarchy_outgoing(file, line, col)
            print(json.dumps(result, indent=2))
        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)
    finally:
        client.stop()
