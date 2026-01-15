import { fireEvent, render, screen } from "@testing-library/react";
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
		fireEvent.click(screen.getAllByRole("button", { name: /Search/i })[1]);
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
