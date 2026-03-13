import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ToolNecessityEditor from "../../../../../src/components/app/editors/ToolNecessityEditor";
import type {
	ExpectedTools,
	ToolCallRecord,
} from "../../../../../src/models/groundTruth";

afterEach(cleanup);

const toolCalls: ToolCallRecord[] = [
	{ id: "1", name: "search", callType: "tool" },
	{ id: "2", name: "lookup", callType: "tool" },
];

describe("ToolNecessityEditor", () => {
	it("renders a row for each unique tool name", () => {
		const onUpdate = vi.fn();
		render(
			<ToolNecessityEditor
				toolCalls={toolCalls}
				expectedTools={undefined}
				onUpdate={onUpdate}
			/>,
		);
		expect(screen.getByText("search")).toBeInTheDocument();
		expect(screen.getByText("lookup")).toBeInTheDocument();
	});

	it("includes tool names from expectedTools that are not in toolCalls", () => {
		const onUpdate = vi.fn();
		const expected: ExpectedTools = {
			required: [{ name: "summarize" }],
		};
		render(
			<ToolNecessityEditor
				toolCalls={toolCalls}
				expectedTools={expected}
				onUpdate={onUpdate}
			/>,
		);
		expect(screen.getByText("summarize")).toBeInTheDocument();
	});

	it("shows correct active state for a required tool", () => {
		const onUpdate = vi.fn();
		const expected: ExpectedTools = {
			required: [{ name: "search" }],
		};
		render(
			<ToolNecessityEditor
				toolCalls={toolCalls}
				expectedTools={expected}
				onUpdate={onUpdate}
			/>,
		);
		const requiredBtn = screen.getByRole("button", {
			name: "Set search to Required",
		});
		expect(requiredBtn).toHaveAttribute("aria-pressed", "true");
	});

	it("toggles tool from required to optional", () => {
		const onUpdate = vi.fn();
		const expected: ExpectedTools = {
			required: [{ name: "search" }],
			optional: [{ name: "lookup" }],
		};
		render(
			<ToolNecessityEditor
				toolCalls={toolCalls}
				expectedTools={expected}
				onUpdate={onUpdate}
			/>,
		);
		const optionalBtn = screen.getByRole("button", {
			name: "Set search to Optional",
		});
		fireEvent.click(optionalBtn);

		expect(onUpdate).toHaveBeenCalledOnce();
		const result = onUpdate.mock.calls[0][0] as ExpectedTools;
		expect(result.required?.map((t) => t.name) ?? []).not.toContain("search");
		expect(result.optional?.map((t) => t.name) ?? []).toContain("search");
	});

	it("toggles tool from optional to not-needed", () => {
		const onUpdate = vi.fn();
		const expected: ExpectedTools = {
			optional: [{ name: "search" }],
		};
		render(
			<ToolNecessityEditor
				toolCalls={toolCalls}
				expectedTools={expected}
				onUpdate={onUpdate}
			/>,
		);
		const notNeededBtn = screen.getByRole("button", {
			name: "Set search to Not needed",
		});
		fireEvent.click(notNeededBtn);

		expect(onUpdate).toHaveBeenCalledOnce();
		const result = onUpdate.mock.calls[0][0] as ExpectedTools;
		expect(result.optional?.map((t) => t.name) ?? []).not.toContain("search");
		expect(result.notNeeded?.map((t) => t.name) ?? []).toContain("search");
	});

	it("preserves expectation arguments when moving a tool between buckets", () => {
		const onUpdate = vi.fn();
		const expected: ExpectedTools = {
			optional: [
				{
					name: "search",
					arguments: { query: "ground truth curator" },
				},
			],
		};
		render(
			<ToolNecessityEditor
				toolCalls={toolCalls}
				expectedTools={expected}
				onUpdate={onUpdate}
			/>,
		);
		fireEvent.click(
			screen.getByRole("button", {
				name: "Set search to Required",
			}),
		);

		expect(onUpdate).toHaveBeenCalledOnce();
		const result = onUpdate.mock.calls[0][0] as ExpectedTools;
		expect(result.optional?.map((t) => t.name) ?? []).not.toContain("search");
		expect(result.required).toEqual([
			{
				name: "search",
				arguments: { query: "ground truth curator" },
			},
		]);
	});

	it("shows empty state when no tool calls exist", () => {
		const onUpdate = vi.fn();
		render(
			<ToolNecessityEditor
				toolCalls={[]}
				expectedTools={undefined}
				onUpdate={onUpdate}
			/>,
		);
		expect(screen.getByText("No tool calls to classify.")).toBeInTheDocument();
	});

	it("preserves other tools when toggling one tool", () => {
		const onUpdate = vi.fn();
		const expected: ExpectedTools = {
			required: [{ name: "search" }, { name: "lookup" }],
		};
		render(
			<ToolNecessityEditor
				toolCalls={toolCalls}
				expectedTools={expected}
				onUpdate={onUpdate}
			/>,
		);
		const optionalBtn = screen.getByRole("button", {
			name: "Set search to Optional",
		});
		fireEvent.click(optionalBtn);

		const result = onUpdate.mock.calls[0][0] as ExpectedTools;
		expect(result.required?.map((t) => t.name) ?? []).toContain("lookup");
		expect(result.required?.map((t) => t.name) ?? []).not.toContain("search");
		expect(result.optional?.map((t) => t.name) ?? []).toContain("search");
	});
});
