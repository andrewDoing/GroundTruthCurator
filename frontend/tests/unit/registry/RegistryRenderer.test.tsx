import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fieldComponentRegistry } from "../../../src/registry/FieldComponentRegistry";
import { RegistryRenderer } from "../../../src/registry/RegistryRenderer";
import type { RenderContext, ViewerProps } from "../../../src/registry/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ctx: RenderContext = {
	itemId: "item-1",
	fieldPath: "plugins.test",
	readOnly: false,
};

function MockViewer({ data }: ViewerProps) {
	return <div data-testid="mock-viewer">{JSON.stringify(data)}</div>;
}

function BoomComponent(): never {
	throw new Error("Plugin crashed!");
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RegistryRenderer", () => {
	beforeEach(() => {
		fieldComponentRegistry.reset();
	});

	// ── Fallbacks ───────────────────────────────────────────────────────────

	it("renders fallback when no registration exists", () => {
		render(
			<RegistryRenderer
				discriminator="unknown"
				data={{ key: "value" }}
				context={ctx}
				mode="viewer"
			/>,
		);

		// KVDict fallback renders key-value pairs
		expect(screen.getByText("key:")).toBeInTheDocument();
		expect(screen.getByText("value")).toBeInTheDocument();
	});

	it("renders KVDictFallback for object data without registration", () => {
		render(
			<RegistryRenderer
				discriminator="missing"
				data={{ alpha: 1, beta: "two" }}
				context={ctx}
				mode="viewer"
			/>,
		);

		expect(screen.getByText("alpha:")).toBeInTheDocument();
		expect(screen.getByText("1")).toBeInTheDocument();
		expect(screen.getByText("beta:")).toBeInTheDocument();
		expect(screen.getByText("two")).toBeInTheDocument();
	});

	it("renders CodeBlockFallback for string data without registration", () => {
		render(
			<RegistryRenderer
				discriminator="missing"
				data="hello world"
				context={ctx}
				mode="viewer"
			/>,
		);

		expect(screen.getByText("hello world")).toBeInTheDocument();
		// CodeBlockFallback wraps in <code>
		const code = screen.getByText("hello world").closest("code");
		expect(code).toBeInTheDocument();
	});

	it("renders JsonFallback for array data without registration", () => {
		render(
			<RegistryRenderer
				discriminator="missing"
				data={[1, 2, 3]}
				context={ctx}
				mode="viewer"
			/>,
		);

		// JSON fallback uses <pre> with formatted JSON
		const pre = document.querySelector("pre");
		expect(pre).toBeInTheDocument();
		expect(pre?.textContent).toContain("1");
		expect(pre?.textContent).toContain("2");
		expect(pre?.textContent).toContain("3");
	});

	// ── Registered component ────────────────────────────────────────────────

	it("renders registered viewer component", () => {
		fieldComponentRegistry.register({
			discriminator: "custom",
			viewer: MockViewer,
			displayName: "Custom Viewer",
		});

		render(
			<RegistryRenderer
				discriminator="custom"
				data={{ hello: "world" }}
				context={ctx}
				mode="viewer"
			/>,
		);

		expect(screen.getByTestId("mock-viewer")).toBeInTheDocument();
		expect(screen.getByTestId("mock-viewer").textContent).toContain("hello");
	});

	// ── Error boundary ──────────────────────────────────────────────────────

	it("catches plugin errors via PluginErrorBoundary and shows fallback", () => {
		// Suppress expected error boundary logging
		const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

		fieldComponentRegistry.register({
			discriminator: "boom",
			viewer: BoomComponent,
			displayName: "Boom",
		});

		render(
			<RegistryRenderer
				discriminator="boom"
				data={{ oops: true }}
				context={ctx}
				mode="viewer"
			/>,
		);

		// Should render the KVDict fallback instead of crashing
		expect(screen.getByText("oops:")).toBeInTheDocument();
		// The mock-viewer should NOT be in the document
		expect(screen.queryByTestId("mock-viewer")).not.toBeInTheDocument();

		errorSpy.mockRestore();
	});
});
