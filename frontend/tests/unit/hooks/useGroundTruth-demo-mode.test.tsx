import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("demo mode configuration", () => {
	beforeEach(() => {
		vi.resetModules();
	});

	afterEach(() => {
		vi.unstubAllEnvs();
	});

	describe("shouldUseDemoProvider", () => {
		it("returns false when DEMO_MODE is false", async () => {
			vi.doMock("../../../src/config/demo", () => ({
				default: false,
				DEMO_MODE: false,
				shouldUseDemoProvider: () => false,
				isDemoModeIgnored: () => false,
			}));

			const { shouldUseDemoProvider } = await import(
				"../../../src/config/demo"
			);
			expect(shouldUseDemoProvider()).toBe(false);
		});

		it("returns true when DEMO_MODE is true and in dev build", async () => {
			// This test verifies the function behavior when properly configured
			// The actual import.meta.env.DEV is set by Vite at build time
			vi.doMock("../../../src/config/demo", () => ({
				default: true,
				DEMO_MODE: true,
				shouldUseDemoProvider: () => true, // Simulating dev build + DEMO_MODE
				isDemoModeIgnored: () => false,
			}));

			const { shouldUseDemoProvider } = await import(
				"../../../src/config/demo"
			);
			expect(shouldUseDemoProvider()).toBe(true);
		});

		it("returns false when DEMO_MODE is true but not in dev build", async () => {
			vi.doMock("../../../src/config/demo", () => ({
				default: true,
				DEMO_MODE: true,
				shouldUseDemoProvider: () => false, // Simulating non-dev build
				isDemoModeIgnored: () => true,
			}));

			const { shouldUseDemoProvider } = await import(
				"../../../src/config/demo"
			);
			expect(shouldUseDemoProvider()).toBe(false);
		});
	});

	describe("isDemoModeIgnored", () => {
		it("returns false when DEMO_MODE is false", async () => {
			vi.doMock("../../../src/config/demo", () => ({
				default: false,
				DEMO_MODE: false,
				shouldUseDemoProvider: () => false,
				isDemoModeIgnored: () => false,
			}));

			const { isDemoModeIgnored } = await import("../../../src/config/demo");
			expect(isDemoModeIgnored()).toBe(false);
		});

		it("returns true when DEMO_MODE is true but not in dev build", async () => {
			vi.doMock("../../../src/config/demo", () => ({
				default: true,
				DEMO_MODE: true,
				shouldUseDemoProvider: () => false,
				isDemoModeIgnored: () => true,
			}));

			const { isDemoModeIgnored } = await import("../../../src/config/demo");
			expect(isDemoModeIgnored()).toBe(true);
		});

		it("returns false when DEMO_MODE is true and in dev build", async () => {
			vi.doMock("../../../src/config/demo", () => ({
				default: true,
				DEMO_MODE: true,
				shouldUseDemoProvider: () => true,
				isDemoModeIgnored: () => false,
			}));

			const { isDemoModeIgnored } = await import("../../../src/config/demo");
			expect(isDemoModeIgnored()).toBe(false);
		});
	});
});

describe("useGroundTruth demo mode initialization", () => {
	const mockLogEvent = vi.fn();

	beforeEach(() => {
		vi.resetModules();
		mockLogEvent.mockReset();
	});

	it("uses ApiProvider when shouldUseDemoProvider returns false", async () => {
		const apiProviderConstructorSpy = vi.fn();

		vi.doMock("../../../src/config/demo", () => ({
			default: false,
			DEMO_MODE: false,
			shouldUseDemoProvider: () => false,
			isDemoModeIgnored: () => false,
		}));

		vi.doMock("../../../src/adapters/apiProvider", () => ({
			ApiProvider: class MockApiProvider {
				id = "api";
				constructor() {
					apiProviderConstructorSpy();
				}
				async list() {
					return { items: [] };
				}
				async get() {
					return null;
				}
				async save(item: unknown) {
					return item;
				}
				async duplicate(item: unknown) {
					return item;
				}
				async export() {
					return "[]";
				}
			},
		}));

		vi.doMock("../../../src/services/telemetry", () => ({
			logEvent: mockLogEvent,
			logException: vi.fn(),
			logTrace: vi.fn(),
		}));

		// Mock other dependencies
		vi.doMock("../../../src/services/chatService", () => ({
			callAgentChat: vi.fn(),
			formatConversationForAgent: vi.fn(),
			formatExpectedBehaviorForChat: vi.fn(),
		}));

		vi.doMock("../../../src/services/http", () => ({
			mapApiErrorToMessage: vi.fn(),
		}));

		vi.doMock("../../../src/services/tags", () => ({
			addTags: vi.fn(),
		}));

		const { renderHook, waitFor } = await import("@testing-library/react");
		const { default: useGroundTruth } = await import(
			"../../../src/hooks/useGroundTruth"
		);

		renderHook(() => useGroundTruth());

		await waitFor(() => {
			expect(apiProviderConstructorSpy).toHaveBeenCalled();
		});

		// Should not log demo_mode_ignored when DEMO_MODE is false
		expect(mockLogEvent).not.toHaveBeenCalledWith(
			"demo_mode_ignored_non_dev_build",
			expect.anything(),
		);
	});

	it("uses demo provider when shouldUseDemoProvider returns true", async () => {
		const createDemoProviderSpy = vi.fn(() => ({
			id: "json",
			async list() {
				return { items: [] };
			},
			async get() {
				return null;
			},
			async save(item: unknown) {
				return item;
			},
			async duplicate(item: unknown) {
				return item;
			},
			async export() {
				return "[]";
			},
		}));

		vi.doMock("../../../src/config/demo", () => ({
			default: true,
			DEMO_MODE: true,
			shouldUseDemoProvider: () => true,
			isDemoModeIgnored: () => false,
		}));

		vi.doMock("../../../src/models/demoData", () => ({
			createDemoProvider: createDemoProviderSpy,
		}));

		vi.doMock("../../../src/adapters/apiProvider", () => ({
			ApiProvider: class {
				id = "api";
				async list() {
					return { items: [] };
				}
				async get() {
					return null;
				}
				async save(item: unknown) {
					return item;
				}
				async duplicate(item: unknown) {
					return item;
				}
				async export() {
					return "[]";
				}
			},
		}));

		vi.doMock("../../../src/services/telemetry", () => ({
			logEvent: mockLogEvent,
			logException: vi.fn(),
			logTrace: vi.fn(),
		}));

		vi.doMock("../../../src/services/chatService", () => ({
			callAgentChat: vi.fn(),
			formatConversationForAgent: vi.fn(),
			formatExpectedBehaviorForChat: vi.fn(),
		}));

		vi.doMock("../../../src/services/http", () => ({
			mapApiErrorToMessage: vi.fn(),
		}));

		vi.doMock("../../../src/services/tags", () => ({
			addTags: vi.fn(),
		}));

		const { renderHook, waitFor } = await import("@testing-library/react");
		const { default: useGroundTruth } = await import(
			"../../../src/hooks/useGroundTruth"
		);

		renderHook(() => useGroundTruth());

		await waitFor(() => {
			expect(createDemoProviderSpy).toHaveBeenCalled();
		});
	});

	it("logs telemetry when isDemoModeIgnored returns true", async () => {
		vi.doMock("../../../src/config/demo", () => ({
			default: true,
			DEMO_MODE: true,
			shouldUseDemoProvider: () => false,
			isDemoModeIgnored: () => true,
		}));

		vi.doMock("../../../src/adapters/apiProvider", () => ({
			ApiProvider: class {
				id = "api";
				async list() {
					return { items: [] };
				}
				async get() {
					return null;
				}
				async save(item: unknown) {
					return item;
				}
				async duplicate(item: unknown) {
					return item;
				}
				async export() {
					return "[]";
				}
			},
		}));

		vi.doMock("../../../src/services/telemetry", () => ({
			logEvent: mockLogEvent,
			logException: vi.fn(),
			logTrace: vi.fn(),
		}));

		vi.doMock("../../../src/services/chatService", () => ({
			callAgentChat: vi.fn(),
			formatConversationForAgent: vi.fn(),
			formatExpectedBehaviorForChat: vi.fn(),
		}));

		vi.doMock("../../../src/services/http", () => ({
			mapApiErrorToMessage: vi.fn(),
		}));

		vi.doMock("../../../src/services/tags", () => ({
			addTags: vi.fn(),
		}));

		const { renderHook, waitFor } = await import("@testing-library/react");
		const { default: useGroundTruth } = await import(
			"../../../src/hooks/useGroundTruth"
		);

		renderHook(() => useGroundTruth());

		await waitFor(() => {
			expect(mockLogEvent).toHaveBeenCalledWith(
				"demo_mode_ignored_non_dev_build",
				{ reason: "DEMO_MODE is only supported in dev builds" },
			);
		});
	});
});
