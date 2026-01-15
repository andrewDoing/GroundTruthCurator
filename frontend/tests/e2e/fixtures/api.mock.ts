import { test as base } from "@playwright/test";

// withApiMocks: fixture to stub network when needed. Currently a no-op since DEMO_MODE uses in-memory data and mocks.
// Extend later with page.routeFromHAR or bespoke route.fulfill for /v1/search.
export const test = base.extend({
	// page: async ({ page }, use) => {
	//   // Example: await page.routeFromHAR('playwright/fixtures/backend.har', { notFound: 'fallback' });
	//   await use(page);
	// },
});

export const expect = test.expect;
