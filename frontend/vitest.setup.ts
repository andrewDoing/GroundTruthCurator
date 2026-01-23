// Extend Vitest's expect with jest-dom matchers
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// Mock global fetch to prevent network calls in tests
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

// Mock the useTagGlossary hook to prevent async fetch calls during tests
vi.mock("./src/hooks/useTagGlossary", () => ({
	useTagGlossary: () => ({
		glossary: {},
		loading: false,
		error: null,
	}),
	useTagDescription: () => undefined,
	clearGlossaryCache: vi.fn(),
	setMockGlossary: vi.fn(),
}));

// Clear mocks before each test
beforeEach(() => {
	mockFetch.mockClear();
});

// Cleanup after each test to prevent DOM pollution
afterEach(() => {
	cleanup();
	vi.clearAllTimers();
});
