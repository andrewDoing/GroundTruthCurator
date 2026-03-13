/** Demo mode configuration helper.
 * Reads DEMO_MODE (or VITE_DEMO_MODE as fallback) and exposes demo affordances.
 * Explicit `json` keeps the frontend-only provider; truthy values default to API-backed demo mode.
 */

function normalize(v: unknown): string {
	return String(v ?? "")
		.trim()
		.toLowerCase();
}

// Vite exposes only VITE_* by default. We'll also allow plain DEMO_MODE if defined via define.
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
const RAW_DEMO_MODE = import.meta.env.DEMO_MODE as unknown as
	| string
	| undefined;
const RAW_VITE_DEMO_MODE = import.meta.env.VITE_DEMO_MODE as unknown as
	| string
	| undefined;
const DEMO_MODE_VALUE: string = RAW_DEMO_MODE ?? RAW_VITE_DEMO_MODE ?? "";
const NORMALIZED_DEMO_MODE = normalize(DEMO_MODE_VALUE);

const DEMO_MODE: boolean =
	NORMALIZED_DEMO_MODE.length > 0 &&
	!["0", "false", "no", "off"].includes(NORMALIZED_DEMO_MODE);

export type DemoDataSource = "api" | "json";

export function getDemoDataSource(): DemoDataSource | null {
	if (!DEMO_MODE) return null;
	return ["json", "local", "static"].includes(NORMALIZED_DEMO_MODE)
		? "json"
		: "api";
}

/**
 * Determines if the demo provider should be used.
 * Frontend-only demo data is only active in development builds when demo mode
 * explicitly requests the JSON provider.
 * This function is extracted to enable testing of the gating logic.
 */
export function shouldUseDemoProvider(): boolean {
	const inDevBuild = !!import.meta.env.DEV;
	return inDevBuild && getDemoDataSource() === "json";
}

/**
 * Returns true if DEMO_MODE is set but we're not in a dev build.
 * Used to log a telemetry event when demo mode is ignored.
 */
export function isDemoModeIgnored(): boolean {
	const inDevBuild = !!import.meta.env.DEV;
	return !inDevBuild && DEMO_MODE;
}

export default DEMO_MODE;
