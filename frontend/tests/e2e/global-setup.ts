// Global setup for E2E tests: optionally wait for backend health when not in demo mode.
import type { FullConfig } from "@playwright/test";

async function waitFor(url: string, timeoutMs = 60_000): Promise<void> {
	const start = Date.now();
	let lastErr: unknown;
	while (Date.now() - start < timeoutMs) {
		try {
			const res = await fetch(url);
			if (res.ok) return;
			lastErr = new Error(`HTTP ${res.status}`);
		} catch (e) {
			lastErr = e;
		}
		await new Promise((r) => setTimeout(r, 1000));
	}
	throw new Error(`Timed out waiting for ${url} - lastErr=${String(lastErr)}`);
}

export default async function globalSetup(_config: FullConfig) {
	// If tests run against real backend, ensure it's healthy.
	// Respect CI or local env var to toggle. Default to not waiting (demo JSON provider).
	const shouldWait =
		process.env.E2E_WAIT_FOR_BACKEND === "1" || process.env.CI === "1";
	const base = process.env.E2E_BACKEND_URL || "http://localhost:8000";
	if (shouldWait) {
		await waitFor(`${base}/healthz`, 90_000);
	}
}
