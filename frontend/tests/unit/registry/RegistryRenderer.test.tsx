import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { ToolCallRecord } from "../../../src/models/groundTruth";
import { toolCallExtensions } from "../../../src/registry/FieldComponentRegistry";
import { ToolCallExtensionRenderer } from "../../../src/registry/RegistryRenderer";
import type { ToolCallActionProps } from "../../../src/registry/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function MockAction({ toolCall }: ToolCallActionProps) {
	return <div data-testid="mock-action">Action for {toolCall.name}</div>;
}

function makeTc(name: string): ToolCallRecord {
	return { id: "tc-1", name, callType: "tool" };
}

function renderExtension(toolCall: ToolCallRecord) {
	return render(
		<ToolCallExtensionRenderer
			toolCall={toolCall}
			context={{
				item: {
					id: "item-1",
					question: "q",
					answer: "",
					status: "draft",
					providerId: "json",
					tags: [],
				},
				readOnly: false,
			}}
			references={[]}
		/>,
	);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ToolCallExtensionRenderer", () => {
	beforeEach(() => {
		toolCallExtensions.reset();
	});

	it("renders nothing when no extensions match", () => {
		const { container } = renderExtension(makeTc("unknown"));
		expect(container.innerHTML).toBe("");
	});

	it("renders the registered component when a matching tool call is provided", () => {
		toolCallExtensions.register({
			discriminator: "toolCall:search",
			component: MockAction,
			displayName: "Search Action",
		});

		renderExtension(makeTc("search"));

		expect(screen.getByTestId("mock-action")).toBeInTheDocument();
		expect(screen.getByTestId("mock-action").textContent).toContain("search");
	});

	it("renders nothing when discriminator does not match", () => {
		toolCallExtensions.register({
			discriminator: "toolCall:search",
			component: MockAction,
			displayName: "Search Action",
		});

		const { container } = renderExtension(makeTc("other"));
		expect(container.innerHTML).toBe("");
	});
});
