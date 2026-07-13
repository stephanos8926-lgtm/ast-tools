import * as path from "path";
import * as vscode from "vscode";
import { execSync } from "child_process";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  State,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;

export async function activate(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration("ast-tools");
  if (!config.get<boolean>("enable", true)) {
    return;
  }

  // Status bar — tracks lifecycle
  const statusBar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100,
  );
  statusBar.text = "$(sync~spin) ast-tools";
  statusBar.tooltip = "ast-tools: starting...";
  statusBar.show();
  context.subscriptions.push(statusBar);

  // Ensure the Python backend is installed
  const serverInfo = await ensureServer(context, statusBar);
  if (!serverInfo) {
    return; // User declined install, or install failed
  }

  const serverOptions: ServerOptions = {
    command: serverInfo.python,
    args: [serverInfo.module, "lsp"],
    transport: TransportKind.stdio,
    options: {
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    },
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [
      { scheme: "file", language: "python" },
      { scheme: "file", language: "typescript" },
      { scheme: "file", language: "javascript" },
      { scheme: "file", language: "go" },
      { scheme: "file", language: "rust" },
      { scheme: "file", language: "cpp" },
      { scheme: "file", language: "markdown" },
    ],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/ast-tools.yaml"),
    },
    initializationOptions: {
      enable: config.get<boolean>("enable", true),
      configPath: config.get<string>("configPath", ""),
      fixOnSave: config.get<boolean>("fixOnSave", false),
      llmFixes: config.get<boolean>("llmFixes", true),
    },
  };

  client = new LanguageClient(
    "ast-tools",
    "ast-tools Language Server",
    serverOptions,
    clientOptions,
  );

  client.registerProposedFeatures();

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("ast-tools.restart", () => restart(context)),
    vscode.commands.registerCommand("ast-tools.fixAll", () => fixAll()),
    vscode.commands.registerCommand("ast-tools.openConfig", () => openConfig()),
    vscode.commands.registerCommand("ast-tools.llmFix", () => llmFix()),
  );

  // Update status bar on state changes
  client.onDidChangeState((event) => {
    switch (event.newState) {
      case State.Running:
        statusBar.text = "$(check) ast-tools";
        statusBar.tooltip = "ast-tools: connected";
        statusBar.backgroundColor = undefined;
        break;
      case State.Starting:
        statusBar.text = "$(sync~spin) ast-tools";
        statusBar.tooltip = "ast-tools: starting...";
        break;
      case State.Stopped:
        statusBar.text = "$(error) ast-tools";
        statusBar.tooltip = "ast-tools: disconnected";
        statusBar.backgroundColor = new vscode.ThemeColor(
          "statusBarItem.errorBackground",
        );
        break;
    }
  });

  // Start the client
  client.start();
}

export function deactivate(): Thenable<void> | undefined {
  if (!client) {
    return undefined;
  }
  return client.stop();
}

// ─── Server Install ────────────────────────────────────────────────────

interface ServerInfo {
  python: string;
  module: string;
}

async function ensureServer(
  context: vscode.ExtensionContext,
  statusBar: vscode.StatusBarItem,
): Promise<ServerInfo | null> {
  // 1. Try system PATH first (fast path — user has ast-tools installed)
  const systemPython = findSystemPython();
  if (systemPython) {
    try {
      execSync(`${systemPython} -m ast_tools.lsp.server --help`, {
        stdio: "ignore",
        timeout: 5000,
      });
      return { python: systemPython, module: "-m" };
    } catch {
      // ast-tools not installed at system level — fall through
    }
  }

  // 2. Try bundled venv in extension directory
  const venvDir = path.join(context.extensionPath, ".venv");
  const venvPython = getVenvPython(venvDir);
  if (venvPython) {
    try {
      execSync(`${venvPython} -m ast_tools.lsp.server --help`, {
        stdio: "ignore",
        timeout: 5000,
      });
      return { python: venvPython, module: "-m" };
    } catch {
      // Bundled venv exists but ast-tools not installed — reinstall
    }
  }

  // 3. Offer to install
  const install = await vscode.window.showInformationMessage(
    "ast-tools LSP server not found. Install it now? " +
      "(requires Python 3.11+)",
    "Install",
    "Install with pipx (isolated)",
    "Skip",
  );

  if (install === "Skip" || !install) {
    statusBar.text = "$(error) ast-tools";
    statusBar.tooltip = "ast-tools: not installed";
    return null;
  }

  statusBar.text = "$(sync~spin) ast-tools: installing...";
  statusBar.tooltip = "Installing ast-tools...";

  if (install === "Install with pipx (isolated)") {
    return await installWithPipx(statusBar);
  }

  // Default: bundled venv
  return await installBundled(venvDir, venvPython, statusBar);
}

function findSystemPython(): string | null {
  const candidates = ["python3", "python"];
  for (const cmd of candidates) {
    try {
      const result = execSync(`${cmd} --version`, {
        encoding: "utf-8",
        timeout: 3000,
        stdio: "pipe",
      });
      if (result.startsWith("Python 3")) {
        return cmd;
      }
    } catch {
      continue;
    }
  }
  return null;
}

function getVenvPython(venvDir: string): string | null {
  const candidates = [
    path.join(venvDir, "bin", "python"),
    path.join(venvDir, "Scripts", "python.exe"),
  ];
  for (const candidate of candidates) {
    try {
      if (require("fs").existsSync(candidate)) {
        return candidate;
      }
    } catch {
      continue;
    }
  }
  return null;
}

async function installBundled(
  venvDir: string,
  venvPython: string | null,
  statusBar: vscode.StatusBarItem,
): Promise<ServerInfo | null> {
  try {
    // Create venv if it doesn't exist
    if (!venvPython) {
      const python = findSystemPython();
      if (!python) {
        vscode.window.showErrorMessage(
          "Python 3 not found. Install Python 3.11+ and try again.",
        );
        return null;
      }
      execSync(`${python} -m venv "${venvDir}"`, {
        stdio: "pipe",
        timeout: 30000,
      });
      venvPython = getVenvPython(venvDir);
      if (!venvPython) {
        throw new Error("Failed to create virtual environment");
      }
    }

    // Install ast-tools
    const result = execSync(
      `"${venvPython}" -m pip install ast-tools 2>&1`,
      { encoding: "utf-8", timeout: 120000, maxBuffer: 1024 * 1024 },
    );

    if (result.includes("Successfully installed")) {
      vscode.window.showInformationMessage(
        "ast-tools installed successfully!",
      );
    }

    return { python: venvPython, module: "-m" };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(
      `Failed to install ast-tools: ${msg}`,
    );
    return null;
  }
}

async function installWithPipx(
  statusBar: vscode.StatusBarItem,
): Promise<ServerInfo | null> {
  try {
    // Check pipx availability
    execSync("pipx --version", { stdio: "ignore", timeout: 5000 });

    // Install via pipx
    execSync("pipx install ast-tools", {
      stdio: "pipe",
      timeout: 120000,
      maxBuffer: 1024 * 1024,
    });

    vscode.window.showInformationMessage(
      "ast-tools installed via pipx!",
    );

    // pipx installs to ~/.local/bin/ast-tools
    return { python: "ast-tools", module: "" };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(
      `pipx install failed: ${msg}. Install manually: pip install ast-tools`,
    );
    return null;
  }
}

// ─── Commands ──────────────────────────────────────────────────────────

async function restart(context: vscode.ExtensionContext) {
  vscode.window.showInformationMessage("Restarting ast-tools LSP server...");
  await deactivate();
  await activate(context);
}

async function fixAll() {
  if (!client) {
    vscode.window.showErrorMessage("ast-tools not connected");
    return;
  }
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showInformationMessage("No active editor");
    return;
  }
  vscode.commands.executeCommand("editor.action.sourceAction", {
    kind: "source.fixAll",
  });
}

async function openConfig() {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders) {
    vscode.window.showErrorMessage("No workspace open");
    return;
  }
  const configPath = path.join(
    workspaceFolders[0].uri.fsPath,
    "ast-tools.yaml",
  );
  const doc = await vscode.workspace.openTextDocument(
    vscode.Uri.file(configPath),
  );
  vscode.window.showTextDocument(doc);
}

async function llmFix() {
  if (!client) {
    vscode.window.showErrorMessage("ast-tools not connected");
    return;
  }
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return;
  }
  vscode.commands.executeCommand("editor.action.codeAction", {
    kind: "ast-tools.llmFix",
    context: {
      diagnostics: vscode.languages.getDiagnostics(editor.document.uri),
    },
  });
}