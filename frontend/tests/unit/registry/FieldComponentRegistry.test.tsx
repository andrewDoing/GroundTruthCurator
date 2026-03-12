import { beforeEach, describe, expect, it, vi } from "vitest";
import { FieldComponentRegistry } from "../../../src/registry/FieldComponentRegistry";
import type { EditorProps, ViewerProps } from "../../../src/registry/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StubViewer({ data }: ViewerProps) {
	return <div>{JSON.stringify(data)}</div>;
}

function StubEditor({ data, onChange }: EditorProps) {
	return (
		<div>
			{JSON.stringify(data)}
			<button type="button" onClick={() => onChange(null)}>
				edit
			</button>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FieldComponentRegistry", () => {
	let registry: FieldComponentRegistry;

	beforeEach(() => {
		registry = new FieldComponentRegistry();
	});

	// ── register / resolve ──────────────────────────────────────────────────

	it("registers and resolves viewer by exact discriminator", () => {
		registry.register({
			discriminator: "toolCall",
			viewer: StubViewer,
			displayName: "Tool Call",
		});

		expect(registry.resolve("toolCall", "viewer")).toBe(StubViewer);
	});

	it("registers and resolves editor by exact discriminator", () => {
		registry.register({
			discriminator: "toolCall",
			viewer: StubViewer,
			editor: StubEditor,
			displayName: "Tool Call",
		});

		expect(registry.resolve("toolCall", "editor")).toBe(StubEditor);
	});

	it("falls back to viewer when editor is requested but not registered", () => {
		registry.register({
			discriminator: "toolCall",
			viewer: StubViewer,
			displayName: "Tool Call",
		});

		expect(registry.resolve("toolCall", "editor")).toBe(StubViewer);
	});

	// ── prefix matching ─────────────────────────────────────────────────────

	it("resolves via prefix fallback (toolCall → toolCall:retrieval)", () => {
		registry.register({
			discriminator: "toolCall",
			viewer: StubViewer,
			displayName: "Tool Call",
		});

		expect(registry.resolve("toolCall:retrieval", "viewer")).toBe(StubViewer);
	});

	it("does not prefix-match without colon separator", () => {
		registry.register({
			discriminator: "tool",
			viewer: StubViewer,
			displayName: "Tool",
		});

		// "toolCall" starts with "tool" but has no ":" after the prefix
		expect(registry.resolve("toolCall", "viewer")).toBeUndefined();
	});

	// ── unknown discriminator ───────────────────────────────────────────────

	it("returns undefined for unknown discriminator", () => {
		expect(registry.resolve("unknown", "viewer")).toBeUndefined();
	});

	// ── duplicate registration warning ──────────────────────────────────────

	it("logs warning on duplicate registration in dev mode", () => {
		const spy = vi.spyOn(console, "warn").mockImplementation(() => {});

		registry.register({
			discriminator: "dup",
			viewer: StubViewer,
			displayName: "First",
		});
		registry.register({
			discriminator: "dup",
			viewer: StubViewer,
			displayName: "Second",
		});

		expect(spy).toHaveBeenCalledWith(
			"[FieldComponentRegistry] Duplicate registration for discriminator: dup",
		);

		spy.mockRestore();
	});

	// ── has() ───────────────────────────────────────────────────────────────

	it("has() returns true for exact match", () => {
		registry.register({
			discriminator: "toolCall",
			viewer: StubViewer,
			displayName: "Tool Call",
		});

		expect(registry.has("toolCall")).toBe(true);
	});

	it("has() returns true for prefix match", () => {
		registry.register({
			discriminator: "toolCall",
			viewer: StubViewer,
			displayName: "Tool Call",
		});

		expect(registry.has("toolCall:retrieval")).toBe(true);
	});

	it("has() returns false for unknown discriminator", () => {
		expect(registry.has("nope")).toBe(false);
	});

	// ── registrations() ─────────────────────────────────────────────────────

	it("registrations() returns all registered items", () => {
		const regA = {
			discriminator: "a",
			viewer: StubViewer,
			displayName: "A",
		};
		const regB = {
			discriminator: "b",
			viewer: StubViewer,
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
			discriminator: "toolCall",
			viewer: StubViewer,
			displayName: "Tool Call",
		});

		registry.reset();

		expect(registry.registrations()).toHaveLength(0);
		expect(registry.has("toolCall")).toBe(false);
	});
});
