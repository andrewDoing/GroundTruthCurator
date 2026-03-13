import { act, fireEvent, render, screen } from "@testing-library/react";
import ReferencesSection from "../../../../../src/components/app/pages/ReferencesSection";
import type { Reference } from "../../../../../src/models/groundTruth";

const ref = (id: string): Reference => ({
	id,
	url: `http://x/${id}`,
	title: `T-${id}`,
});

describe("ReferencesSection", () => {
	it("runs search and adds refs from results", async () => {
		const onRunSearch = vi.fn();
		const onAddRefs = vi.fn();

		render(
			<ReferencesSection
				query="hello"
				setQuery={vi.fn()}
				searching={false}
				searchResults={[ref("1"), ref("2")]}
				onRunSearch={onRunSearch}
				onAddRefs={onAddRefs}
				references={[]}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		// Switch to Selected and back via buttons
		fireEvent.click(screen.getByRole("button", { name: /Selected \(/i }));
		fireEvent.click(screen.getByRole("button", { name: /^Search$/i }));

		// Select first, add selected
		const cbs = screen.getAllByRole("checkbox");
		fireEvent.click(cbs[0]);
		fireEvent.click(
			screen.getByRole("button", { name: /Add\s+1\s+to Selected/i }),
		);
		expect(onAddRefs).toHaveBeenCalled();

		// Run search
		await act(async () => {
			fireEvent.click(screen.getAllByRole("button", { name: /Search/i })[1]);
		});
		expect(onRunSearch).toHaveBeenCalled();
	});

	it("confirms remove", () => {
		const onRemoveReference = vi.fn();
		vi.spyOn(window, "confirm").mockReturnValue(true);

		render(
			<ReferencesSection
				query=""
				setQuery={vi.fn()}
				searching={false}
				searchResults={[]}
				onRunSearch={vi.fn()}
				onAddRefs={vi.fn()}
				references={[ref("x")]}
				onUpdateReference={vi.fn()}
				onRemoveReference={onRemoveReference}
				onOpenReference={vi.fn()}
			/>,
		);

		// Switch to Selected tab to expose remove
		fireEvent.click(screen.getByRole("button", { name: /Selected \(/i }));
		// Click the remove (trash) button which has title "Remove reference"
		fireEvent.click(screen.getByTitle(/Remove reference/i));
		expect(onRemoveReference).toHaveBeenCalled();
	});
});

// ---------------------------------------------------------------------------
// Phase 4: ReferencesSection as generic right pane
// ---------------------------------------------------------------------------
import type { GroundTruthItem } from "../../../../../src/models/groundTruth";
import { getItemReferences } from "../../../../../src/models/groundTruth";

const makeItem = (
	overrides: Partial<GroundTruthItem> = {},
): GroundTruthItem => ({
	id: "i1",
	question: "Q",
	answer: "A",
	status: "draft",
	providerId: "test",
	...overrides,
});

describe("ReferencesSection – generic right pane (Phase 4)", () => {
	const noopProps = {
		query: "",
		setQuery: vi.fn(),
		searching: false,
		searchResults: [],
		onRunSearch: vi.fn(),
		onAddRefs: vi.fn(),
		references: [],
		onUpdateReference: vi.fn(),
		onRemoveReference: vi.fn(),
		onOpenReference: vi.fn(),
	};

	it("shows TracePanel when item has toolCalls", () => {
		const item = makeItem({
			toolCalls: [{ id: "tc1", name: "search", callType: "tool" }],
		});
		render(<ReferencesSection {...noopProps} item={item} isMultiTurn />);
		expect(screen.getByText(/Evidence & Review/i)).toBeInTheDocument();
	});

	it("does not show the evidence pane when item is null in single-turn mode", () => {
		render(
			<ReferencesSection {...noopProps} item={null} isMultiTurn={false} />,
		);
		expect(screen.queryByText(/Evidence & Review/i)).not.toBeInTheDocument();
		expect(
			screen.queryByText(/No trace or evidence data available yet/i),
		).not.toBeInTheDocument();
		// Search tab should be visible (RAG compat surface)
		const searchBtns = screen.getAllByRole("button", { name: /Search/i });
		expect(searchBtns.length).toBeGreaterThan(0);
	});

	it("shows the trace empty state when multi-turn mode has no evidence yet", () => {
		const item = makeItem(); // no toolCalls, no traceIds, etc.
		render(<ReferencesSection {...noopProps} item={item} isMultiTurn />);
		expect(screen.getByText(/Evidence & Review/i)).toBeInTheDocument();
		expect(
			screen.getByText(/No trace or evidence data available yet/i),
		).toBeInTheDocument();
	});

	it("shows expected-tool details when item has expectedTools without toolCalls", () => {
		const item = makeItem({
			expectedTools: {
				required: [{ name: "search", arguments: { query: "refund policy" } }],
				optional: [{ name: "fetch" }],
			},
			toolCalls: [],
		});
		render(<ReferencesSection {...noopProps} item={item} isMultiTurn />);
		expect(screen.getByText(/Evidence & Review/i)).toBeInTheDocument();
		expect(screen.getByText(/Expected Tools/i)).toBeInTheDocument();
		expect(screen.getByText(/^Required$/i)).toBeInTheDocument();
		expect(screen.getByText(/^Optional$/i)).toBeInTheDocument();
		expect(screen.getByText(/^search$/i)).toBeInTheDocument();
		expect(screen.getByText(/refund policy/i)).toBeInTheDocument();
		expect(screen.getByText(/^fetch$/i)).toBeInTheDocument();
	});

	it("shows generic evidence for context-only items", () => {
		const item = makeItem({
			contextEntries: [
				{ key: "customer_tier", value: "enterprise" },
				{ key: "request", value: { region: "us" } },
			],
		});
		render(<ReferencesSection {...noopProps} item={item} isMultiTurn />);
		expect(screen.getByText(/Evidence & Review/i)).toBeInTheDocument();
		// Context Entries is inside "More Details" collapsible
		expect(screen.getByText(/More Details/i)).toBeInTheDocument();
	});

	it("shows generic plugin-owned details for plugin-only items", () => {
		const item = makeItem({
			plugins: {
				"rag-compat": {
					kind: "retrieval-review",
					version: "1",
					data: {
						retrievalMode: "semantic",
						latencyMs: 42,
					},
				},
			},
		});
		render(<ReferencesSection {...noopProps} item={item} isMultiTurn />);
		expect(screen.getByText(/Evidence & Review/i)).toBeInTheDocument();
		// Plugin Details is inside "More Details" collapsible
		expect(screen.getByText(/More Details/i)).toBeInTheDocument();
	});

	it("shows only evidence panel when multi-turn item has references", () => {
		const item = makeItem({
			toolCalls: [{ id: "tc1", name: "search", callType: "tool" }],
			plugins: {
				"rag-compat": {
					kind: "rag-compat",
					version: "1.0",
					data: {
						retrievals: {
							_unassociated: {
								candidates: [{ url: "https://example.com" }],
							},
						},
					},
				},
			},
		});
		render(
			<ReferencesSection
				{...noopProps}
				item={item}
				references={getItemReferences(item)}
				isMultiTurn
			/>,
		);
		expect(screen.getByText(/Evidence & Review/i)).toBeInTheDocument();
		// RAG references panel is hidden in multi-turn mode
		expect(screen.queryByText(/Selected/i)).not.toBeInTheDocument();
	});
});
