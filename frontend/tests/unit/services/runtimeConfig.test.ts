import { afterEach, describe, expect, it, vi } from "vitest";

const runtimeConfigFixture = {
	requireReferenceVisit: true,
	requireKeyParagraph: false,
	selfServeLimit: 10,
	trustedReferenceDomains: ["example.com"],
};

describe("runtime config base path support", () => {
	afterEach(() => {
		vi.resetModules();
		vi.unstubAllEnvs();
		vi.unstubAllGlobals();
	});

	it("fetches runtime config under the configured base path", async () => {
		vi.stubEnv("BASE_URL", "/gtc/");
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => runtimeConfigFixture,
		});
		vi.stubGlobal("fetch", fetchMock);

		const { getRuntimeConfig } = await import(
			"../../../src/services/runtimeConfig"
		);

		await expect(getRuntimeConfig()).resolves.toEqual(runtimeConfigFixture);
		expect(fetchMock).toHaveBeenCalledWith("/gtc/v1/config");
	});
});
