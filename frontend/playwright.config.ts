import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(configDir, "..");
const backendRoot = path.join(repoRoot, "backend");
const frontendRoot = configDir;
const backendPort = process.env.PLAYWRIGHT_BACKEND_PORT ?? "8010";
const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT ?? "4174";
const backendUrl =
	process.env.PLAYWRIGHT_BACKEND_URL ?? `http://127.0.0.1:${backendPort}`;
const frontendUrl =
	process.env.PLAYWRIGHT_FRONTEND_URL ?? `http://127.0.0.1:${frontendPort}`;
const cosmosEndpoint =
	process.env.PLAYWRIGHT_COSMOS_ENDPOINT ?? "http://127.0.0.1:8081";
const cosmosKey =
	process.env.PLAYWRIGHT_COSMOS_KEY ??
	"C2y6yDjf5/R+ob0N8A7Cgv30VRDjEWEhLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==";
const devUser = process.env.PLAYWRIGHT_DEV_USER ?? "playwright-e2e@example.com";

const sh = (value: string) => JSON.stringify(value);

export default defineConfig({
	testDir: "./tests/e2e",
	fullyParallel: false,
	workers: 1,
	timeout: 90_000,
	expect: {
		timeout: 15_000,
	},
	use: {
		baseURL: frontendUrl,
		trace: "retain-on-failure",
		screenshot: "only-on-failure",
		video: "retain-on-failure",
	},
	projects: [
		{
			name: "chromium",
			use: {
				...devices["Desktop Chrome"],
				viewport: { width: 1440, height: 1100 },
			},
		},
	],
	webServer: [
		{
			command: [
				`cd ${sh(repoRoot)}`,
				[
					"python3 -c",
					sh(
						"import socket, sys, urllib.parse; " +
							`u=urllib.parse.urlparse(${JSON.stringify(cosmosEndpoint)}); ` +
							"host=u.hostname or '127.0.0.1'; " +
							"port=u.port or 8081; " +
							"sock=socket.create_connection((host, port), timeout=5); " +
							"sock.close()",
					),
				].join(" "),
				`cd ${sh(backendRoot)}`,
				[
					"env",
					`GTC_COSMOS_ENDPOINT=${sh(cosmosEndpoint)}`,
					`GTC_COSMOS_KEY=${sh(cosmosKey)}`,
					"uv run python scripts/cosmos_container_manager.py",
					`--endpoint ${sh(cosmosEndpoint)}`,
					`--key ${sh(cosmosKey)}`,
					"--no-verify",
					"--db gt-curator",
					"--gt-container ground_truth",
					"--assignments-container assignments",
					"--tags-container tags",
					"--tag-definitions-container tag_definitions",
				].join(" "),
				[
					"env",
					"GTC_ENV_FILE=environments/sample.env",
					"GTC_AUTH_MODE=dev",
					"GTC_REPO_BACKEND=cosmos",
					`GTC_COSMOS_ENDPOINT=${sh(cosmosEndpoint)}`,
					`GTC_COSMOS_KEY=${sh(cosmosKey)}`,
					"GTC_COSMOS_DB_NAME=gt-curator",
					"GTC_USE_COSMOS_EMULATOR=true",
					"GTC_COSMOS_CONNECTION_VERIFY=false",
					"GTC_COSMOS_TEST_MODE=false",
					"GTC_EZAUTH_ENABLED=false",
					`uv run uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
				].join(" "),
			].join(" && "),
			url: `${backendUrl}/healthz`,
			timeout: 120_000,
			reuseExistingServer: false,
		},
		{
			command: [
				`cd ${sh(frontendRoot)}`,
				[
					"env",
					`HARNESS_BACKEND_URL=${sh(backendUrl)}`,
					`VITE_DEV_USER_ID=${sh(devUser)}`,
					`npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
				].join(" "),
			].join(" && "),
			url: frontendUrl,
			timeout: 120_000,
			reuseExistingServer: false,
		},
	],
});
