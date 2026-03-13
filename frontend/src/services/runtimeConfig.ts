/**
 * Runtime configuration fetched from backend.
 *
 * This provides a centralized way to access backend configuration values
 * that can be changed without rebuilding the frontend.
 */

import { useSyncExternalStore } from "react";
import type { components } from "../api/generated";
import { getApiBaseUrl } from "./http";

export type RuntimeConfig = components["schemas"]["FrontendConfig"];

let cachedConfig: RuntimeConfig | null = null;
let configPromise: Promise<RuntimeConfig> | null = null;
const listeners = new Set<() => void>();

function notifyListeners() {
	for (const listener of listeners) {
		listener();
	}
}

function setCachedConfig(config: RuntimeConfig) {
	cachedConfig = config;
	notifyListeners();
}

function buildFallbackConfig(): RuntimeConfig {
	const trustedDomainsRaw =
		(import.meta.env.VITE_TRUSTED_REFERENCE_DOMAINS as string | undefined) ??
		"";
	const trustedReferenceDomains = trustedDomainsRaw
		.split(",")
		.map((d) => d.trim().toLowerCase())
		.filter(Boolean);

	return {
		requireReferenceVisit: getEnvBoolean("VITE_REQUIRE_REFERENCE_VISIT", true),
		requireKeyParagraph: getEnvBoolean("VITE_REQUIRE_KEY_PARAGRAPH", false),
		selfServeLimit: getEnvNumber("VITE_SELF_SERVE_LIMIT", 10),
		trustedReferenceDomains,
	};
}

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
			const response = await fetch(`${getApiBaseUrl()}/config`);
			if (response.ok) {
				const config: RuntimeConfig = await response.json();
				setCachedConfig(config);
				return config;
			}
		} catch (error) {
			console.warn(
				"Failed to fetch runtime config from backend, using defaults:",
				error,
			);
		}

		const fallbackConfig = buildFallbackConfig();
		setCachedConfig(fallbackConfig);
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

export function subscribeToRuntimeConfig(listener: () => void) {
	listeners.add(listener);
	return () => {
		listeners.delete(listener);
	};
}

export function getRuntimeConfigSnapshot(): RuntimeConfig | null {
	return cachedConfig;
}

/**
 * Synchronously get cached config (must call getRuntimeConfig first).
 * Returns null if config not yet loaded.
 */
export function getCachedConfig(): RuntimeConfig | null {
	return getRuntimeConfigSnapshot();
}

export function useRuntimeConfig(): RuntimeConfig | null {
	return useSyncExternalStore(
		subscribeToRuntimeConfig,
		getRuntimeConfigSnapshot,
		getRuntimeConfigSnapshot,
	);
}
