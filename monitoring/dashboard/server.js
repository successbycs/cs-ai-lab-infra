const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const port = Number(process.env.HEALTH_DASHBOARD_PORT || "8080");
const dashboardPath = path.join(process.env.HEALTH_DASHBOARD_OUTPUT_DIR || "/opt/health-dashboard/output", "index.html");
const emptyPage = `<!doctype html><html lang="en-NZ"><meta charset="utf-8"><title>CS AI Lab Health</title><body><h1>CS AI Lab Health</h1><p>No Healthcheck result has been published yet.</p></body></html>`;

http.createServer((request, response) => {
  if (request.url === "/healthz") {
    response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
    response.end('{"status":"ok"}');
    return;
  }
  if (request.method !== "GET" || !["/", "/index.html"].includes(request.url)) {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found\n");
    return;
  }
  const body = fs.existsSync(dashboardPath) ? fs.readFileSync(dashboardPath) : emptyPage;
  response.writeHead(200, {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
  });
  response.end(body);
}).listen(port, "0.0.0.0", () => console.log(`Health dashboard listening on ${port}`));
