/// <reference types="node" />

import process from "node:process";
import { cleanupSeededData } from "./setup/api-seeder";
import { readStateFile, removeFile } from "./setup/backend-manager";
import {
	INTEGRATION_STATE_FILE,
	type IntegrationState,
	loadIntegrationState,
} from "./setup/integration-helpers";

async function terminateProcess(pid: number): Promise<void> {
	if (pid <= 0) return;
	const send = (signal: NodeJS.Signals) => {
		try {
			process.kill(pid, signal);
		} catch (err) {
			if ((err as { code?: string }).code === "ESRCH") return;
			throw err;
		}
	};

	const isAlive = () => {
		try {
			process.kill(pid, 0);
			return true;
		} catch (err) {
			return (err as { code?: string }).code !== "ESRCH";
		}
	};

	send("SIGTERM");
	const deadline = Date.now() + 5_000;
	while (Date.now() < deadline) {
		if (!isAlive()) return;
		await new Promise((resolve) => setTimeout(resolve, 200));
	}
	send("SIGKILL");
}

export default async function globalTeardown(): Promise<void> {
	const state =
		(await loadIntegrationState()) ??
		(await readStateFile<IntegrationState>(INTEGRATION_STATE_FILE));
	if (!state) {
		console.warn(
			`[globalTeardown] No integration state found at ${INTEGRATION_STATE_FILE}. Skipping cleanup. This may leave test data in your database.`,
		);
		return;
	}

	console.log(
		`[globalTeardown] Found state file. Cleaning up ${state.seeded.length} seeded items from database ${state.cosmosDbName}`,
	);

	try {
		await cleanupSeededData(state, state.backend.url, state.devUserId);
		console.log("[globalTeardown] Successfully cleaned up seeded data");
	} catch (err) {
		console.warn(`Failed to cleanup seeded data: ${String(err)}`);
	}

	try {
		await terminateProcess(state.backend.pid);
		console.log(
			`[globalTeardown] Successfully terminated backend process ${state.backend.pid}`,
		);
	} catch (err) {
		console.warn(`Failed to terminate backend process: ${String(err)}`);
	}

	await removeFile(INTEGRATION_STATE_FILE);
	console.log(`[globalTeardown] Removed state file ${INTEGRATION_STATE_FILE}`);
}
