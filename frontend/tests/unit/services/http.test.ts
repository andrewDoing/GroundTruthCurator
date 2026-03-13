import { afterEach, describe, expect, it, vi } from "vitest";

describe("http base path helpers", () => {
	afterEach(() => {
		vi.resetModules();
		vi.unstubAllEnvs();
	});

	it("keeps API paths at the root by default", async () => {
		const http = await import("../../../src/services/http");

		expect(http.getAppBasePath()).toBe("");
		expect(http.getApiBaseUrl()).toBe("/v1");
		expect(http.prefixAppBasePath("/v1/config")).toBe("/v1/config");
	});

	it("prefixes root-relative paths when BASE_URL is configured", async () => {
		vi.stubEnv("BASE_URL", "/gtc/");
		const http = await import("../../../src/services/http");

		expect(http.getAppBasePath()).toBe("/gtc");
		expect(http.getApiBaseUrl()).toBe("/gtc/v1");
		expect(http.prefixAppBasePath("/v1/config")).toBe("/gtc/v1/config");
	});

	it("avoids double-prefixing paths that already include the base path", async () => {
		vi.stubEnv("BASE_URL", "/gtc/");
		const http = await import("../../../src/services/http");

		expect(http.prefixAppBasePath("/gtc/v1/config")).toBe("/gtc/v1/config");
		expect(http.prefixAppBasePath("https://example.com/v1/config")).toBe(
			"https://example.com/v1/config",
		);
	});
});
