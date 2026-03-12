import { act, fireEvent, render, screen } from "@testing-library/react";
import ReferencesSection from "../../../../../src/components/app/pages/ReferencesSection";
import type {
	GroundTruthItem,
	Reference,
} from "../../../../../src/models/groundTruth";
import { getItemReferences } from "../../../../../src/models/groundTruth";

const ref = (id: string): Reference => ({
	id,
	url: `http://x/${id}`,
	title: `T-${id}`,
});

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

describe("ReferencesSection", () => {
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

	it("runs search and adds refs from results on the compatibility search surface", async () => {
		const onRunSearch = vi.fn();
		const onAddRefs = vi.fn();

		render(
			<ReferencesSection
				{...noopProps}
				query="hello"
				searchResults={[ref("1"), ref("2")]}
				onRunSearch={onRunSearch}
				onAddRefs={onAddRefs}
				references={[]}
				isMultiTurn={false}
			/>,
		);

		const cbs = screen.getAllByRole("checkbox");
		fireEvent.click(cbs[0]);
		fireEvent.click(
			screen.getByRole("button", { name: /Attach 1 selected result/i }),
		);
		expect(onAddRefs).toHaveBeenCalled();

		await act(async () => {
			fireEvent.click(screen.getByRole("button", { name: /^Search$/i }));
		});
		expect(onRunSearch).toHaveBeenCalled();
	});

	it("confirms remove from the evidence review surface", () => {
		const onRemoveReference = vi.fn();
		vi.spyOn(window, "confirm").mockReturnValue(true);

		render(
			<ReferencesSection
				{...noopProps}
				references={[ref("x")]}
				onRemoveReference={onRemoveReference}
				isMultiTurn={false}
			/>,
		);

		fireEvent.click(screen.getByTitle(/Remove reference/i));
		expect(onRemoveReference).toHaveBeenCalled();
	});

	it("shows generic evidence panel when item has toolCalls", () => {
		const item = makeItem({
			toolCalls: [{ id: "tc1", name: "search", callType: "tool" }],
		});
		render(<ReferencesSection {...noopProps} item={item} isMultiTurn />);
		expect(screen.getByText(/Evidence & Review/i)).toBeInTheDocument();
	});

	it("shows host-owned search only in single-turn compatibility mode", () => {
		render(
			<ReferencesSection {...noopProps} item={null} isMultiTurn={false} />,
		);
		expect(screen.getByText(/Search Evidence/i)).toBeInTheDocument();
	});

	it("shows review-only guidance when multi-turn mode has no generic evidence", () => {
		render(
			<ReferencesSection
				{...noopProps}
				references={[{ ...ref("t1"), turnId: "turn-agent-1" }]}
				isMultiTurn
			/>,
		);
		expect(screen.queryByText(/Search Evidence/i)).toBeNull();
		expect(
			screen.getByText(/plugin-specific evidence surfaces/i),
		).toBeInTheDocument();
	});

	it("shows empty state when no evidence or review surface is available", () => {
		const item = makeItem();
		render(<ReferencesSection {...noopProps} item={item} isMultiTurn />);
		expect(
			screen.getByText(/No evidence or review surfaces are available/i),
		).toBeInTheDocument();
	});

	it("shows registry-backed evidence panel for plugin-only items", () => {
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
		expect(screen.getByText(/More Details/i)).toBeInTheDocument();
	});

	it("keeps multi-turn references in review without restoring global tabs", () => {
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
		expect(screen.queryByText(/^Search Evidence$/i)).toBeNull();
		expect(
			screen.getByText(/Review Attached Evidence \(1\)/i),
		).toBeInTheDocument();
	});
});
