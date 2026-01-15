/**
 * Runtime configuration fetched from backend.
 *
 * This provides a centralized way to access backend configuration values
 * that can be changed without rebuilding the frontend.
 */

import type { components } from "../api/generated";

type RuntimeConfig = components["schemas"]["FrontendConfig"];

let cachedConfig: RuntimeConfig | null = null;
let configPromise: Promise<RuntimeConfig> | null = null;

/**
 * Fetch runtime configuration from backend.
 * Results are cached after first fetch.
 * Falls back to environment variables if backend is unavailable.
 */
export async function getRuntimeConfig(): Promise<RuntimeConfig> {
	// Return cached config if available
	if (cachedConfig) {
		return cachedConfig;
	}

	// Return in-flight promise if already fetching
	if (configPromise) {
		return configPromise;
	}

	// Fetch config from backend
	configPromise = (async () => {
		try {
			const response = await fetch("/v1/config");
			if (response.ok) {
				const config: RuntimeConfig = await response.json();
				cachedConfig = config;
				return config;
			}
		} catch (error) {
			console.warn(
				"Failed to fetch runtime config from backend, using defaults:",
				error,
			);
		}

		// Fallback to environment variables (for local dev)
		const trustedDomainsRaw = (import.meta.env
			.VITE_TRUSTED_REFERENCE_DOMAINS as string | undefined) ?? "";
		const trustedReferenceDomains = trustedDomainsRaw
			.split(",")
			.map((d) => d.trim().toLowerCase())
			.filter(Boolean);

		const fallbackConfig: RuntimeConfig = {
			requireReferenceVisit: getEnvBoolean(
				"VITE_REQUIRE_REFERENCE_VISIT",
				true,
			),
			requireKeyParagraph: getEnvBoolean("VITE_REQUIRE_KEY_PARAGRAPH", false),
			selfServeLimit: getEnvNumber("VITE_SELF_SERVE_LIMIT", 10),
			trustedReferenceDomains,
		};
		cachedConfig = fallbackConfig;
		return fallbackConfig;
	})();

	return configPromise;
}

/**
 * Get boolean value from environment variable with fallback.
 */
function getEnvBoolean(key: string, defaultValue: boolean): boolean {
	const val = import.meta.env[key];
	if (val === undefined || val === null) return defaultValue;
	if (typeof val === "boolean") return val;
	return val !== "false" && val !== "0";
}

/**
 * Get number value from environment variable with fallback.
 */
function getEnvNumber(key: string, defaultValue: number): number {
	const val = import.meta.env[key];
	if (val === undefined || val === null) return defaultValue;
	if (typeof val === "number") return val;
	const parsed = Number(val);
	return Number.isNaN(parsed) ? defaultValue : parsed;
}

/**
 * Synchronously get cached config (must call getRuntimeConfig first).
 * Returns null if config not yet loaded.
 */
export function getCachedConfig(): RuntimeConfig | null {
	return cachedConfig;
}
