import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;
const baseURL = isCI ? "http://localhost:4173" : "http://localhost:5173";

export default defineConfig({
	testDir: "tests/e2e",
	testIgnore: "**/*-integration.spec.ts",
	timeout: 30_000,
	expect: { timeout: 5_000 },
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	retries: isCI ? 1 : 0,
	workers: 2,
	reporter: [
		["list"],
		["html", { outputFolder: "playwright-report", open: "never" }],
	],
	globalSetup: "./tests/e2e/global-setup.ts",
	use: {
		baseURL,
		trace: "retain-on-failure",
		screenshot: "only-on-failure",
		video: "retain-on-failure",
	},
	webServer: isCI
		? [
				{
					command:
						"VITE_DEMO_MODE=1 npm run -s build && VITE_DEMO_MODE=1 npm run -s preview -- --host --port 4173",
					port: 4173,
					reuseExistingServer: true,
					env: { VITE_DEMO_MODE: "1", DEMO_MODE: "1" },
					timeout: 120_000,
				},
			]
		: [
				{
					command: "VITE_DEMO_MODE=1 npm run -s dev -- --host --port 5173",
					port: 5173,
					// Always start a fresh dev server to ensure VITE_DEMO_MODE=1 is applied
					reuseExistingServer: false,
					env: { VITE_DEMO_MODE: "1", DEMO_MODE: "1" },
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
