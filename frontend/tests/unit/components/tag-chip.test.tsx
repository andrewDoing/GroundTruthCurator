import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TagChip from "../../../src/components/common/TagChip";

describe("TagChip", () => {
	it("renders manual tag with violet styling", () => {
		render(<TagChip tag="manual:tag" />);
		const chip = screen.getByText("manual:tag").closest("span");
		expect(chip).toHaveClass("bg-violet-100", "text-violet-800");
		expect(chip).not.toHaveClass("bg-slate-100");
	});

	it("renders computed tag with slate styling and lock icon", () => {
		render(<TagChip tag="computed:tag" isComputed />);
		const chip = screen.getByText("computed:tag").closest("span");
		expect(chip).toHaveClass("bg-slate-100", "text-slate-600");
		expect(chip).toHaveClass("border-slate-200");
		expect(chip).not.toHaveClass("bg-violet-100");
	});

	it("shows remove button only for manual tags", () => {
		const onRemove = vi.fn();
		render(<TagChip tag="manual:tag" onRemove={onRemove} />);
		const removeButton = screen.getByRole("button");
		expect(removeButton).toBeInTheDocument();
		expect(removeButton).toHaveAttribute("aria-label", "Remove manual:tag");
	});

	it("does not show remove button for computed tags", () => {
		const onRemove = vi.fn();
		render(<TagChip tag="computed:tag" isComputed onRemove={onRemove} />);
		const removeButton = screen.queryByRole("button");
		expect(removeButton).not.toBeInTheDocument();
	});

	it("does not show remove button when onRemove is not provided", () => {
		render(<TagChip tag="manual:tag" />);
		const removeButton = screen.queryByRole("button");
		expect(removeButton).not.toBeInTheDocument();
	});

	it("calls onRemove when remove button clicked", () => {
		const onRemove = vi.fn();
		render(<TagChip tag="manual:tag" onRemove={onRemove} />);
		const removeButton = screen.getByRole("button");
		fireEvent.click(removeButton);
		expect(onRemove).toHaveBeenCalledTimes(1);
	});

	it("applies custom className", () => {
		render(<TagChip tag="test" className="custom-class" />);
		const chip = screen.getByText("test").closest("span");
		expect(chip).toHaveClass("custom-class");
	});
});
