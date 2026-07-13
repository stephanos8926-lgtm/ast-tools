import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  State,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;

export function activate(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration("ast-tools");
  if (!config.get<boolean>("enable", true)) {
    return;
  }

  const serverCommand = config.get<string>("binaryPath", "ast-tools");
  const serverArgs = ["lsp"];

  const serverOptions: ServerOptions = {
    command: serverCommand,
    args: serverArgs,
    transport: TransportKind.stdio,
    options: {
      env: { ...process.env },
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

  // Create status bar item
  const statusBar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100,
  );
  statusBar.text = "$(sync~spin) ast-tools";
  statusBar.tooltip = "ast-tools: starting...";
  statusBar.show();
  context.subscriptions.push(statusBar);

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

async function restart(context: vscode.ExtensionContext) {
  vscode.window.showInformationMessage("Restarting ast-tools LSP server...");
  await deactivate();
  activate(context);
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

  const selection = editor.selection;
  const uri = editor.document.uri.toString();

  vscode.commands.executeCommand("editor.action.codeAction", {
    kind: "ast-tools.llmFix",
    context: {
      diagnostics: vscode.languages.getDiagnostics(editor.document.uri),
    },
  });
}