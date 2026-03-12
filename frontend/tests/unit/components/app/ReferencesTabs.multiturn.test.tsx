import { render, screen } from "@testing-library/react";
import type { RefObject } from "react";
import ReferencesTabs from "../../../../src/components/app/ReferencesPanel/ReferencesTabs";
import type { Reference } from "../../../../src/models/groundTruth";

describe("ReferencesTabs evidence surfaces", () => {
	type Props = Parameters<typeof ReferencesTabs>[0];
	const makeProps = (): Props => ({
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
		showSearch: true,
	});

	it("renders search and review surfaces when host-owned search is enabled", () => {
		render(<ReferencesTabs {...makeProps()} />);
		expect(screen.getByText(/Evidence Review/i)).toBeInTheDocument();
		expect(screen.getByText(/Search Evidence/i)).toBeInTheDocument();
		expect(
			screen.getByText(/Review Attached Evidence \(0\)/i),
		).toBeInTheDocument();
	});

	it("replaces global tabs with guidance when search is plugin-owned", () => {
		render(<ReferencesTabs {...makeProps()} showSearch={false} />);
		expect(screen.queryByText(/^Search Evidence$/i)).toBeNull();
		expect(
			screen.getByText(/plugin-specific evidence surfaces/i),
		).toBeInTheDocument();
		expect(
			screen.getByText(/Review Attached Evidence \(0\)/i),
		).toBeInTheDocument();
	});
});
