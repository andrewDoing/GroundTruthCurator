/** Demo mode configuration helper.
 * Reads DEMO_MODE (or VITE_DEMO_MODE as fallback) and exposes a boolean flag.
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

const DEMO_MODE: boolean = ["1", "true", "yes", "on"].includes(
	normalize(DEMO_MODE_VALUE),
);

/**
 * Determines if the demo provider should be used.
 * Demo mode is only active in development builds when DEMO_MODE is enabled.
 * This function is extracted to enable testing of the gating logic.
 */
export function shouldUseDemoProvider(): boolean {
	const inDevBuild = !!import.meta.env.DEV;
	return inDevBuild && DEMO_MODE;
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
