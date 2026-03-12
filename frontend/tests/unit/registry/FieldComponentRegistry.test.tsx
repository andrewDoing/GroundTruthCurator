import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ToolCallRecord } from "../../../src/models/groundTruth";
import {
	ToolCallExtensions,
	toolCallDiscriminator,
} from "../../../src/registry/FieldComponentRegistry";
import type {
	ToolCallActionProps,
	ToolCallExtensionRegistration,
} from "../../../src/registry/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StubAction(_props: ToolCallActionProps) {
	return <div>stub</div>;
}

function makeTc(
	name: string,
	overrides?: Partial<ToolCallRecord>,
): ToolCallRecord {
	return { id: "tc-1", name, callType: "tool", ...overrides };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ToolCallExtensions", () => {
	let registry: ToolCallExtensions;

	beforeEach(() => {
		registry = new ToolCallExtensions();
	});

	// ── register / resolveAll ───────────────────────────────────────────────

	it("registers and resolves by exact discriminator", () => {
		registry.register({
			discriminator: "toolCall:search",
			component: StubAction,
			displayName: "Search",
		});

		const matches = registry.resolveAll(makeTc("search"));
		expect(matches).toHaveLength(1);
		expect(matches[0].component).toBe(StubAction);
	});

	// ── prefix matching ─────────────────────────────────────────────────────

	it("resolves via prefix fallback (toolCall matches toolCall:retrieval)", () => {
		registry.register({
			discriminator: "toolCall",
			component: StubAction,
			displayName: "Catch-all",
		});

		const matches = registry.resolveAll(makeTc("retrieval"));
		expect(matches).toHaveLength(1);
		expect(matches[0].displayName).toBe("Catch-all");
	});

	it("does not prefix-match without colon separator", () => {
		registry.register({
			discriminator: "tool",
			component: StubAction,
			displayName: "Tool",
		});

		// "toolCall:foo" starts with "tool" but "tool" is not followed by ":"
		const matches = registry.resolveAll(makeTc("foo"));
		expect(matches).toHaveLength(0);
	});

	// ── matches predicate ───────────────────────────────────────────────────

	it("filters by matches predicate when provided", () => {
		registry.register({
			discriminator: "toolCall:search",
			component: StubAction,
			displayName: "Search with args",
			matches: (tc) => tc.arguments?.query !== undefined,
		});

		expect(registry.resolveAll(makeTc("search"))).toHaveLength(0);
		expect(
			registry.resolveAll(makeTc("search", { arguments: { query: "hello" } })),
		).toHaveLength(1);
	});

	// ── no match ────────────────────────────────────────────────────────────

	it("returns empty for unknown discriminator", () => {
		expect(registry.resolveAll(makeTc("unknown"))).toHaveLength(0);
	});

	// ── duplicate registration warning ──────────────────────────────────────

	it("logs warning on duplicate registration in dev mode", () => {
		const spy = vi.spyOn(console, "warn").mockImplementation(() => {});

		registry.register({
			discriminator: "dup",
			component: StubAction,
			displayName: "First",
		});
		registry.register({
			discriminator: "dup",
			component: StubAction,
			displayName: "Second",
		});

		expect(spy).toHaveBeenCalledWith(
			"[ToolCallExtensions] Replacing registration for discriminator: dup",
		);

		spy.mockRestore();
	});

	// ── hasMatch() ──────────────────────────────────────────────────────────

	it("hasMatch() returns true for matching tool call", () => {
		registry.register({
			discriminator: "toolCall:search",
			component: StubAction,
			displayName: "Search",
		});

		expect(registry.hasMatch(makeTc("search"))).toBe(true);
	});

	it("hasMatch() returns true for prefix match", () => {
		registry.register({
			discriminator: "toolCall",
			component: StubAction,
			displayName: "Catch-all",
		});

		expect(registry.hasMatch(makeTc("retrieval"))).toBe(true);
	});

	it("hasMatch() returns false for unknown tool call", () => {
		expect(registry.hasMatch(makeTc("nope"))).toBe(false);
	});

	// ── registrations() ─────────────────────────────────────────────────────

	it("registrations() returns all registered items", () => {
		const regA: ToolCallExtensionRegistration = {
			discriminator: "toolCall:a",
			component: StubAction,
			displayName: "A",
		};
		const regB: ToolCallExtensionRegistration = {
			discriminator: "toolCall:b",
			component: StubAction,
			displayName: "B",
		};

		registry.register(regA);
		registry.register(regB);

		const all = registry.registrations();
		expect(all).toHaveLength(2);
		expect(all).toContainEqual(regA);
		expect(all).toContainEqual(regB);
	});

	// ── reset() ─────────────────────────────────────────────────────────────

	it("reset() clears all registrations", () => {
		registry.register({
			discriminator: "toolCall:search",
			component: StubAction,
			displayName: "Search",
		});

		registry.reset();

		expect(registry.registrations()).toHaveLength(0);
		expect(registry.hasMatch(makeTc("search"))).toBe(false);
	});

	// ── toolCallDiscriminator ───────────────────────────────────────────────

	it("toolCallDiscriminator builds correct string", () => {
		expect(toolCallDiscriminator(makeTc("search"))).toBe("toolCall:search");
		expect(toolCallDiscriminator(makeTc("retrieval"))).toBe(
			"toolCall:retrieval",
		);
	});
});
