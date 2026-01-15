/// <reference types="node" />

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import type { FullConfig } from "@playwright/test";
import { seedQuestionsExplorerData } from "./setup/api-seeder";
import {
	type BackendProcess,
	removeFile,
	startBackendServer,
	stopBackendServer,
	waitForBackendHealth,
	writeStateFile,
} from "./setup/backend-manager";
import {
	INTEGRATION_STATE_FILE,
	type IntegrationState,
	mergeEnv,
	parseEnvFile,
	toProcessEnv,
	waitForApiReady,
} from "./setup/integration-helpers";

function ensurePrefixed(env: Record<string, string>): void {
	const mappings: Array<[string, string]> = [
		["COSMOS_ENDPOINT", "GTC_COSMOS_ENDPOINT"],
		["COSMOS_KEY", "GTC_COSMOS_KEY"],
		["COSMOS_DB_NAME", "GTC_COSMOS_DB_NAME"],
		["COSMOS_CONTAINER_GT", "GTC_COSMOS_CONTAINER_GT"],
		["COSMOS_CONTAINER_ASSIGNMENTS", "GTC_COSMOS_CONTAINER_ASSIGNMENTS"],
		["COSMOS_CONTAINER_TAGS", "GTC_COSMOS_CONTAINER_TAGS"],
		["COSMOS_CONNECTION_VERIFY", "GTC_COSMOS_CONNECTION_VERIFY"],
		["USE_COSMOS_EMULATOR", "GTC_USE_COSMOS_EMULATOR"],
		["COSMOS_TEST_MODE", "GTC_COSMOS_TEST_MODE"],
		["AUTH_MODE", "GTC_AUTH_MODE"],
	];
	for (const [plain, prefixed] of mappings) {
		if (env[plain] && !env[prefixed]) env[prefixed] = env[plain];
	}
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
	const moduleDir = path.dirname(fileURLToPath(import.meta.url));
	const frontendRoot = path.resolve(moduleDir, "..", "..");
	const backendRoot = path.resolve(frontendRoot, "..", "backend");
	const envFilePath = path.resolve(frontendRoot, ".env.e2e.integration");
	const venvPython = path.resolve(backendRoot, ".venv", "bin", "python");
	const venvExists = await fs
		.access(venvPython)
		.then(() => true)
		.catch(() => false);

	console.log(
		`[globalSetup] Starting setup. State file path: ${INTEGRATION_STATE_FILE}`,
	);
	await removeFile(INTEGRATION_STATE_FILE);

	let backend: BackendProcess | undefined;

	try {
		const fileEnv = await parseEnvFile(envFilePath);
		const runId = process.env.PLAYWRIGHT_RUN_ID || Date.now().toString(36);
		const backendPort = Number.parseInt(fileEnv.BACKEND_PORT ?? "8000", 10);
		const backendHost = fileEnv.BACKEND_HOST || "127.0.0.1";
		const backendUrl = `http://${backendHost}:${backendPort}`;

		const dbBase =
			fileEnv.GTC_COSMOS_DB_NAME || fileEnv.COSMOS_DB_NAME || "gtc-e2e-tests";
		const cosmosDbName = `${dbBase}-${runId}`;
		const devUserId = fileEnv.VITE_DEV_USER_ID || "integration-tests@local";
		const rawEndpoint =
			fileEnv.COSMOS_ENDPOINT ??
			fileEnv.GTC_COSMOS_ENDPOINT ??
			"http://localhost:8081/";
		const cosmosEndpoint = rawEndpoint.startsWith("https://localhost")
			? rawEndpoint.replace("https://", "http://")
			: rawEndpoint.startsWith("https://127.0.0.1")
				? rawEndpoint.replace("https://", "http://")
				: rawEndpoint;

		const overrides = {
			GTC_ENV: fileEnv.GTC_ENV ?? "integration",
			GTC_REPO_BACKEND: "cosmos",
			GTC_AUTH_MODE: fileEnv.GTC_AUTH_MODE ?? fileEnv.AUTH_MODE ?? "dev",
			GTC_COSMOS_DB_NAME: cosmosDbName,
			COSMOS_DB_NAME: cosmosDbName,
			GTC_COSMOS_TEST_MODE: "0",
			COSMOS_TEST_MODE: "0",
			GTC_USE_COSMOS_EMULATOR: fileEnv.GTC_USE_COSMOS_EMULATOR ?? "1",
			COSMOS_USE_EMULATOR:
				fileEnv.COSMOS_USE_EMULATOR ?? fileEnv.GTC_USE_COSMOS_EMULATOR ?? "1",
			GTC_COSMOS_ENDPOINT: cosmosEndpoint,
			COSMOS_ENDPOINT: cosmosEndpoint,
			COSMOS_KEY: fileEnv.COSMOS_KEY ?? fileEnv.GTC_COSMOS_KEY ?? "",
			COSMOS_CONTAINER_GT:
				fileEnv.COSMOS_CONTAINER_GT ?? fileEnv.GTC_COSMOS_CONTAINER_GT ?? "",
			COSMOS_CONTAINER_ASSIGNMENTS:
				fileEnv.COSMOS_CONTAINER_ASSIGNMENTS ??
				fileEnv.GTC_COSMOS_CONTAINER_ASSIGNMENTS ??
				"",
			COSMOS_CONTAINER_TAGS:
				fileEnv.COSMOS_CONTAINER_TAGS ??
				fileEnv.GTC_COSMOS_CONTAINER_TAGS ??
				"",
			COSMOS_CONNECTION_VERIFY:
				fileEnv.COSMOS_CONNECTION_VERIFY ??
				fileEnv.GTC_COSMOS_CONNECTION_VERIFY ??
				"",
			PYTHONUNBUFFERED: "1",
		};
		const merged = mergeEnv(fileEnv, overrides);
		ensurePrefixed(merged);
		const backendEnv = toProcessEnv(merged);
		backendEnv.PYTHONPATH = backendEnv.PYTHONPATH
			? `${backendEnv.PYTHONPATH}:${path.resolve(backendRoot)}`
			: path.resolve(backendRoot);
		console.log(
			"[integration] cosmos override",
			JSON.stringify(
				{
					runId,
					expected: cosmosDbName,
					prefixed: backendEnv.GTC_COSMOS_DB_NAME,
					plain: backendEnv.COSMOS_DB_NAME,
				},
				null,
				2,
			),
		);

		const logDir = path.resolve(frontendRoot, "test-results/integration-logs");
		console.log(
			`[globalSetup] Starting backend on port ${backendPort} using ${venvExists ? "venv" : "system"} Python`,
		);
		backend = await startBackendServer({
			port: backendPort,
			cwd: backendRoot,
			env: backendEnv,
			logDir,
			pythonExecutable: venvExists ? venvPython : undefined,
		});

		console.log(
			`[globalSetup] Backend started (PID ${backend.pid}), waiting for health check...`,
		);
		await waitForBackendHealth(`${backendUrl}/healthz`);
		await waitForApiReady(backendUrl);

		const healthRes = await fetch(`${backendUrl}/healthz`);
		if (!healthRes.ok) {
			throw new Error(
				`Backend health check failed with ${healthRes.status}: ${await healthRes.text()}`,
			);
		}
		const healthJson = (await healthRes.json().catch(() => ({}))) as {
			cosmos?: { db?: string };
		};
		const reportedDb = healthJson?.cosmos?.db;
		if (reportedDb && reportedDb !== cosmosDbName) {
			throw new Error(
				`Backend connected to unexpected Cosmos DB. Expected ${cosmosDbName}, got ${reportedDb}`,
			);
		}

		const seedResult = await seedQuestionsExplorerData(
			backendUrl,
			devUserId,
			runId,
		);

		const state: IntegrationState = {
			runId,
			backend: {
				port: backendPort,
				url: backendUrl,
				pid: backend.pid,
				logFile: backend.logFile,
			},
			cosmosDbName,
			tags: seedResult.blueprint.tags,
			blueprint: seedResult.blueprint,
			seeded: seedResult.seeded,
			devUserId,
		};

		await writeStateFile(INTEGRATION_STATE_FILE, state);
		console.log(
			`[globalSetup] Successfully wrote state file to ${INTEGRATION_STATE_FILE}`,
		);
		console.log(
			`[globalSetup] Seeded ${state.seeded.length} items in database ${state.cosmosDbName}`,
		);

		process.env.E2E_BACKEND_URL = backendUrl;
		process.env.E2E_WAIT_FOR_BACKEND = "1";
		process.env.PLAYWRIGHT_INTEGRATION = "1";
		process.env.PLAYWRIGHT_RUN_ID = runId;
		process.env.VITE_DEV_USER_ID = devUserId;
		process.env.PLAYWRIGHT_INTEGRATION_STATE = INTEGRATION_STATE_FILE;
	} catch (err) {
		console.error(`[globalSetup] Setup failed with error: ${String(err)}`);
		if (backend) {
			console.log("[globalSetup] Stopping backend due to setup failure");
			await stopBackendServer(backend);
		}
		throw err;
	}
}
