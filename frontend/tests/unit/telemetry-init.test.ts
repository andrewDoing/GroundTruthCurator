import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// We'll dynamically import the modules after mocking to isolate module state per test

describe("initTelemetry no-op scenarios", () => {
	beforeEach(() => {
		vi.resetModules();
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.resetModules();
	});

	it("no-ops in demo mode (DEMO_MODE=true)", async () => {
		// Force DEMO_MODE to true by mocking the demo config module
		vi.doMock("../../src/config/demo", () => ({
			default: true,
			DEMO_MODE: true,
			DEMO_MODE_VALUE: "true",
			shouldUseDemoProvider: () => true,
			isDemoModeIgnored: () => false,
		}));

		const telemetry = await import("../../src/services/telemetry");
		const { NoopTelemetry } = await import("../../src/models/telemetry");

		await telemetry.initTelemetry();
		expect(telemetry.getTelemetry()).toBe(NoopTelemetry);

		// Should be safe to call and not throw
		expect(() => telemetry.logEvent("gtc.test")).not.toThrow();
	});

	it("no-ops when backend is otlp but required config is missing", async () => {
		// Use a clean module instance without DEMO_MODE mocked
		const telemetry = await import("../../src/services/telemetry");
		const { NoopTelemetry } = await import("../../src/models/telemetry");

		// Explicitly choose otlp with missing exporter URL and no App Insights fallback
		await telemetry.initTelemetry({
			backend: "otlp",
			otlpUrl: undefined,
			appInsightsConnectionString: undefined,
		});
		expect(telemetry.getTelemetry()).toBe(NoopTelemetry);

		// Safe no-op behavior
		expect(() => telemetry.logException(new Error("x"))).not.toThrow();
	});
});
