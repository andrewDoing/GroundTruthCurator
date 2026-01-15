import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;
const frontendPort = Number.parseInt(process.env.FRONTEND_PORT ?? "5173", 10);
const frontendHost = process.env.FRONTEND_HOST || "127.0.0.1";
const baseURL = `http://${frontendHost}:${frontendPort}`;

export default defineConfig({
	testDir: "tests/e2e",
	testMatch: "**/*-integration.spec.ts",
	timeout: 60_000,
	expect: { timeout: 7_500 },
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: isCI ? 1 : 0,
	workers: 2,
	reporter: [
		["list"],
		["html", { outputFolder: "playwright-report", open: "never" }],
	],
	globalSetup: "./tests/e2e/global-setup-integration.ts",
	globalTeardown: "./tests/e2e/global-teardown-integration.ts",
	use: {
		baseURL,
		trace: "retain-on-failure",
		screenshot: "only-on-failure",
		video: "retain-on-failure",
	},
	webServer: [
		{
			command: `VITE_DEMO_MODE=0 DEMO_MODE=0 npm run -s dev -- --host ${frontendHost} --port ${frontendPort}`,
			port: frontendPort,
			reuseExistingServer: false,
			env: {
				VITE_DEMO_MODE: "0",
				DEMO_MODE: "0",
				VITE_DEV_USER_ID:
					process.env.VITE_DEV_USER_ID || "integration-tests@local",
			},
			timeout: 120_000,
		},
	],
	projects: [
		{
			name: "chromium",
			use: { ...devices["Desktop Chrome"] },
		},
	],
});
