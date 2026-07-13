"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const path = __importStar(require("path"));
const vscode = __importStar(require("vscode"));
const node_1 = require("vscode-languageclient/node");
let client;
function activate(context) {
    const config = vscode.workspace.getConfiguration("ast-tools");
    if (!config.get("enable", true)) {
        return;
    }
    const serverCommand = config.get("binaryPath", "ast-tools");
    const serverArgs = ["lsp"];
    const serverOptions = {
        command: serverCommand,
        args: serverArgs,
        transport: node_1.TransportKind.stdio,
        options: {
            env: { ...process.env },
        },
    };
    const clientOptions = {
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
            enable: config.get("enable", true),
            configPath: config.get("configPath", ""),
            fixOnSave: config.get("fixOnSave", false),
            llmFixes: config.get("llmFixes", true),
        },
    };
    client = new node_1.LanguageClient("ast-tools", "ast-tools Language Server", serverOptions, clientOptions);
    client.registerProposedFeatures();
    // Register commands
    context.subscriptions.push(vscode.commands.registerCommand("ast-tools.restart", () => restart(context)), vscode.commands.registerCommand("ast-tools.fixAll", () => fixAll()), vscode.commands.registerCommand("ast-tools.openConfig", () => openConfig()), vscode.commands.registerCommand("ast-tools.llmFix", () => llmFix()));
    // Create status bar item
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.text = "$(sync~spin) ast-tools";
    statusBar.tooltip = "ast-tools: starting...";
    statusBar.show();
    context.subscriptions.push(statusBar);
    client.onDidChangeState((event) => {
        switch (event.newState) {
            case node_1.State.Running:
                statusBar.text = "$(check) ast-tools";
                statusBar.tooltip = "ast-tools: connected";
                statusBar.backgroundColor = undefined;
                break;
            case node_1.State.Starting:
                statusBar.text = "$(sync~spin) ast-tools";
                statusBar.tooltip = "ast-tools: starting...";
                break;
            case node_1.State.Stopped:
                statusBar.text = "$(error) ast-tools";
                statusBar.tooltip = "ast-tools: disconnected";
                statusBar.backgroundColor = new vscode.ThemeColor("statusBarItem.errorBackground");
                break;
        }
    });
    // Start the client
    client.start();
}
function deactivate() {
    if (!client) {
        return undefined;
    }
    return client.stop();
}
async function restart(context) {
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
    const configPath = path.join(workspaceFolders[0].uri.fsPath, "ast-tools.yaml");
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(configPath));
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
//# sourceMappingURL=extension.js.map