import express from "express";
import path from "path";
import fs from "fs";
import { spawn, ChildProcess } from "child_process";
import { createProxyMiddleware } from "http-proxy-middleware";
import { createServer as createViteServer } from "vite";

const HOST = "127.0.0.1";
const PORT = 3001; // Avoids port 3000 collision
const FLASK_PORT = 5000;
let flaskProcess: ChildProcess | null = null;

function startFlaskBackend() {
  console.log("Starting Python Flask backend on port", FLASK_PORT);
  const pythonCmd = process.platform === "win32" ? "python" : "python3";
  flaskProcess = spawn(pythonCmd, ["backend/app.py"], {
    env: {
      ...process.env,
      FLASK_HOST: HOST,
      FLASK_PORT: String(FLASK_PORT),
      PYTHONUNBUFFERED: "1",
    },
    stdio: "inherit",
  });

  flaskProcess.on("error", (err) => {
    console.error("Failed to start Flask backend:", err);
  });

  flaskProcess.on("exit", (code, signal) => {
    console.log(`Flask backend exited with code ${code}, signal ${signal}`);
  });
}

async function startServer() {
  startFlaskBackend();

  const app = express();

  // 1. Proxy API routes to Flask
  app.use(
    "/api",
    createProxyMiddleware({
      target: `http://${HOST}:${FLASK_PORT}`,
      changeOrigin: true,
      ws: false,
      proxyTimeout: 120000,
      timeout: 120000,
      on: {
        error: (err, req, res) => {
          console.error("Proxy error:", err.message);
          const response = res as express.Response;
          if (!response.headersSent && typeof response.status === "function") {
            response.status(502).json({
              success: false,
              error: "Flask backend unavailable. Please try again.",
            });
          }
        },
      },
    })
  );

  // 2. Vite Dev Server & Frontend Routing
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "custom",
    });

    app.use(vite.middlewares);

    app.get("*", async (req, res, next) => {
      const url = req.originalUrl;
      if (url.startsWith("/api")) {
        return next();
      }

      try {
        const indexPath = path.resolve(process.cwd(), "index.html");
        let template = fs.readFileSync(indexPath, "utf-8");
        template = await vite.transformIndexHtml(url, template);
        res.status(200).set({ "Content-Type": "text/html" }).end(template);
      } catch (e: any) {
        vite.ssrFixStacktrace(e);
        next(e);
      }
    });
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res, next) => {
      if (req.originalUrl.startsWith("/api")) {
        return next();
      }
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  const server = app.listen(PORT, HOST, () => {
    console.log(`File Slicer server running on http://${HOST}:${PORT}`);
  });

  const shutdown = () => {
    console.log("Shutting down servers...");
    if (flaskProcess) {
      flaskProcess.kill("SIGTERM");
    }
    server.close(() => {
      process.exit(0);
    });
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

startServer().catch((err) => {
  console.error("Error starting server:", err);
  if (flaskProcess) {
    flaskProcess.kill();
  }
  process.exit(1);
});