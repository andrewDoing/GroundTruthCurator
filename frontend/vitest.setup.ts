// Extend Vitest's expect with jest-dom matchers
import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock global fetch to prevent network calls in tests
// This is especially important for hooks like useTagGlossary that fetch on mount
const mockFetch = vi.fn(() =>
	Promise.resolve({
		ok: true,
		status: 200,
		json: () => Promise.resolve({ groups: [] }),
		text: () => Promise.resolve(""),
		headers: new Headers(),
	} as Response),
);

global.fetch = mockFetch;
