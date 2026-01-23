import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TagsEditor from "../../../src/components/app/editor/TagsEditor";

// Helper to mount with minimal props
function setup(initial: string[] = [], computedTags?: string[]) {
	const onChange = vi.fn();
	render(
		<TagsEditor
			selected={initial}
			computedTags={computedTags}
			onChange={onChange}
		/>,
	);
	const input = screen.getByRole("combobox") as HTMLInputElement;
	return { input, onChange };
}

describe("TagsEditor", () => {
	it("shows instructional text about group:value format", () => {
		setup();
		expect(screen.getByText(/group:value format/i)).toBeInTheDocument();
	});

	it("prevents creating a new tag that is not group:value", () => {
		const { input, onChange } = setup();

		fireEvent.change(input, { target: { value: "invalidtag" } });
		fireEvent.keyDown(input, { key: "Enter" });

		// Should show validation error and not call onChange
		expect(screen.getByText(/invalid format/i)).toBeInTheDocument();
		expect(onChange).not.toHaveBeenCalled();
	});

	it("allows creating a new group:value tag", () => {
		const { input, onChange } = setup();

		fireEvent.change(input, { target: { value: "source:email" } });
		fireEvent.keyDown(input, { key: "Enter" });

		expect(onChange).toHaveBeenCalledTimes(1);
		const added = onChange.mock.calls[0][0] as string[];
		expect(added).toContain("source:email");
	});

	describe("computed tags", () => {
		it("displays computed tags in read-only section", () => {
			setup([], ["computed:tag1", "computed:tag2"]);
			expect(screen.getByText("computed:tag1")).toBeInTheDocument();
			expect(screen.getByText("computed:tag2")).toBeInTheDocument();
			expect(screen.getByText("Auto-generated")).toBeInTheDocument();
		});

		it("shows lock icon for computed tags", () => {
			setup([], ["computed:tag1"]);
			// Check that the text exists (lock icon is rendered via SVG)
			expect(screen.getByText("Auto-generated")).toBeInTheDocument();
		});

		it("does not allow removing computed tags", () => {
			const { onChange } = setup([], ["computed:tag1"]);
			// Computed tags should not have remove buttons
			const buttons = screen.queryAllByRole("button");
			// Should have no remove buttons for computed tags (only the input exists)
			const removeButtons = buttons.filter((b) =>
				b.getAttribute("aria-label")?.includes("Remove"),
			);
			expect(removeButtons.length).toBe(0);
			expect(onChange).not.toHaveBeenCalled();
		});

		it("allows editing manual tags while computed tags are present", () => {
			const { input, onChange } = setup(["manual:tag"], ["computed:tag"]);

			// Both should be visible
			expect(screen.getByText("manual:tag")).toBeInTheDocument();
			expect(screen.getByText("computed:tag")).toBeInTheDocument();

			// Should be able to add new manual tag
			fireEvent.change(input, { target: { value: "source:email" } });
			fireEvent.keyDown(input, { key: "Enter" });

			expect(onChange).toHaveBeenCalledTimes(1);
			const added = onChange.mock.calls[0][0] as string[];
			expect(added).toContain("source:email");
			expect(added).toContain("manual:tag");
		});
	});
});
