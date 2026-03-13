import { afterEach, describe, expect, it, vi } from "vitest";

describe("demo config parsing", () => {
	afterEach(() => {
		vi.resetModules();
		vi.unstubAllEnvs();
	});

	it("treats truthy demo mode as API-backed by default", async () => {
		vi.stubEnv("VITE_DEMO_MODE", "true");
		const config = await import("../../../src/config/demo");

		expect(config.default).toBe(true);
		expect(config.getDemoDataSource()).toBe("api");
		expect(config.shouldUseDemoProvider()).toBe(false);
	});

	it("uses the JSON provider only when explicitly requested", async () => {
		vi.stubEnv("VITE_DEMO_MODE", "json");
		const config = await import("../../../src/config/demo");

		expect(config.default).toBe(true);
		expect(config.getDemoDataSource()).toBe("json");
		expect(config.shouldUseDemoProvider()).toBe(true);
	});
});
