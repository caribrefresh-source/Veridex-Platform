# mcp-builder

Build a new MCP (Model Context Protocol) server from scratch or extend an existing one.

## What is an MCP Server?

An MCP server exposes **tools**, **resources**, and **prompts** to Claude via a standard protocol. Claude calls tools, reads resources, and uses prompts just like built-in capabilities.

## Workflow

### 1. Define the MCP

Answer these before writing code:
- **Name**: what will it be called in `.mcp.json`?
- **Tools**: what actions should Claude be able to take? (list verb+noun: `search_docs`, `create_issue`, `run_query`)
- **Resources**: what read-only data should Claude be able to browse? (file trees, API schemas, docs)
- **Transport**: `stdio` (default, local process) or `sse` (HTTP server)
- **Auth**: API key via env var? OAuth? None?

### 2. Scaffold (TypeScript — recommended)

```bash
mkdir mcp-<name> && cd mcp-<name>
npm init -y
npm install @modelcontextprotocol/sdk zod
npm install -D typescript @types/node tsx
```

`src/index.ts` skeleton:
```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "mcp-<name>", version: "1.0.0" });

// Register a tool
server.tool(
  "tool_name",
  "Description of what this tool does",
  { param: z.string().describe("Parameter description") },
  async ({ param }) => {
    // Implementation
    return { content: [{ type: "text", text: `Result: ${param}` }] };
  }
);

// Register a resource
server.resource(
  "resource://name/{id}",
  "Description of resource",
  async (uri) => ({
    contents: [{ uri: uri.toString(), mimeType: "text/plain", text: "content" }]
  })
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

### 3. Build & Test

```bash
npx tsx src/index.ts
# Or build:
npx tsc && node dist/index.js
```

Test with MCP Inspector:
```bash
npx @modelcontextprotocol/inspector npx tsx src/index.ts
```

### 4. Wire into `.mcp.json`

```json
{
  "mcpServers": {
    "<name>": {
      "command": "npx",
      "args": ["-y", "tsx", "/absolute/path/to/src/index.ts"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

Add the name to `enabledMcpjsonServers` in `.claude/settings.json`, then restart Claude Code.

### 5. Tool Design Principles

- **One tool = one action**: `search_repos` not `manage_github`
- **Descriptive names and descriptions**: Claude uses these to decide when to call the tool
- **Zod validation on all inputs**: Claude may pass wrong types
- **Return structured text**: JSON or markdown Claude can reason over
- **Error messages as content** (not thrown errors): `return { content: [{ type: "text", text: "Error: ..." }] }`
- **Idempotent where possible**: tools may be called multiple times

### 6. Publishing (optional)

```bash
# package.json: add "bin" field pointing to compiled entry
npm publish --access public
# Users can then: npx -y mcp-<name>
```

## Output

Working MCP server with: tool definitions, Zod schemas, transport setup, `.mcp.json` entry, and test confirmation via MCP Inspector.
