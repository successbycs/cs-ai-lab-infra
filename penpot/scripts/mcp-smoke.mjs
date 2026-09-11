#!/usr/bin/env node

const [endpoint, tokenFile] = process.argv.slice(2);
if (!endpoint || !tokenFile) {
  console.error("usage: mcp-smoke.mjs <base-endpoint> <token-file>");
  process.exit(4);
}

const fs = await import("node:fs");
const token = fs.readFileSync(tokenFile, "utf8").trim();
if (!token || token.length < 20) {
  throw new Error("MCP token file is empty or invalid");
}
const url = `${endpoint}?userToken=${encodeURIComponent(token)}`;

function parsePayload(body) {
  const dataLine = body.split("\n").find((line) => line.startsWith("data: "));
  return JSON.parse(dataLine ? dataLine.slice(6) : body);
}

async function post(id, method, params, sessionId) {
  const headers = {
    "content-type": "application/json",
    accept: "application/json, text/event-stream",
  };
  if (sessionId) headers["mcp-session-id"] = sessionId;
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({ jsonrpc: "2.0", id, method, params }),
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`MCP ${method} returned HTTP ${response.status}`);
  return { payload: parsePayload(body), sessionId: response.headers.get("mcp-session-id") || sessionId };
}

const initialized = await post(1, "initialize", {
  protocolVersion: "2025-03-26",
  capabilities: {},
  clientInfo: { name: "penpot-infrastructure-smoke", version: "1.0.0" },
});
const sessionId = initialized.sessionId;
if (!sessionId) throw new Error("MCP initialization did not return a session ID");

await fetch(url, {
  method: "POST",
  headers: {
    "content-type": "application/json",
    accept: "application/json, text/event-stream",
    "mcp-session-id": sessionId,
  },
  body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }),
});

const listed = await post(2, "tools/list", {}, sessionId);
const toolNames = listed.payload.result.tools.map((tool) => tool.name).sort();
const expectedTools = ["execute_code", "export_shape", "get_high_level_overview", "get_penpot_api_info"];
if (JSON.stringify(toolNames) !== JSON.stringify(expectedTools)) {
  throw new Error(`Unexpected remote-mode tools: ${toolNames.join(",")}`);
}

const info = await post(3, "tools/call", {
  name: "get_penpot_api_info",
  arguments: {},
}, sessionId);
if (info.payload.error || info.payload.result?.isError) {
  throw new Error("MCP read-only API information operation failed");
}

console.log(`PENPOT_MCP_SMOKE_OK tools=${toolNames.length} read_only=true filesystem_tools=false`);
