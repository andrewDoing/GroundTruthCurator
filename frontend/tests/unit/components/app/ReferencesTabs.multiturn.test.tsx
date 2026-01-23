import { render, screen } from "@testing-library/react";
import type { RefObject } from "react";
import type { RightTab } from "../../../../src/components/app/ReferencesPanel/ReferencesTabs";
import ReferencesTabs from "../../../../src/components/app/ReferencesPanel/ReferencesTabs";
import type { Reference } from "../../../../src/models/groundTruth";

describe("ReferencesTabs multi-turn gating", () => {
	type Props = Parameters<typeof ReferencesTabs>[0];
	const makeProps = (): Props => ({
		rightTab: "selected" as RightTab,
		setRightTab: vi.fn(),
		query: "",
		setQuery: vi.fn(),
		searching: false,
		searchResults: [] as Reference[],
		searchSelected: new Set<string>(),
		onRunSearch: vi.fn(),
		onToggleSearchSelect: vi.fn(),
		onAddSelectedFromResults: vi.fn(),
		onAddSingleResult: vi.fn(),
		searchInputRef: { current: null } as RefObject<HTMLInputElement | null>,
		references: [] as Reference[],
		onUpdateReference: vi.fn(),
		onRemoveReference: vi.fn(),
		onOpenReference: vi.fn(),
		isMultiTurn: false,
	});

	it("forces selected tab and hides search when multi-turn is active", () => {
		const props = makeProps();
		props.rightTab = "search";
		props.isMultiTurn = true;
		render(<ReferencesTabs {...props} />);
		expect(props.setRightTab).toHaveBeenCalledWith("selected");
		expect(screen.queryByRole("button", { name: /search/i })).toBeNull();
	});

	it("renders guidance banner in multi-turn mode", () => {
		const props = makeProps();
		props.isMultiTurn = true;
		render(<ReferencesTabs {...props} />);
		expect(
			screen.getByText(/Per-turn reference management enabled/i),
		).toBeInTheDocument();
	});

	it("shows search tab when multi-turn is disabled", () => {
		const props = makeProps();
		props.rightTab = "search";
		render(<ReferencesTabs {...props} />);
		const buttons = screen.getAllByRole("button", { name: /search/i });
		expect(buttons.some((btn) => btn.getAttribute("title") === "Search")).toBe(
			true,
		);
	});
});
