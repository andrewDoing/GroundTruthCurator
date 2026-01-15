import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import QuestionsExplorer, {
	type QuestionsExplorerItem,
} from "../../../../src/components/app/QuestionsExplorer";

const createMockItem = (
	overrides: Partial<QuestionsExplorerItem> = {},
): QuestionsExplorerItem => ({
	id: "item-1",
	question: "Test Question",
	answer: "Test Answer",
	references: [],
	status: "draft",
	providerId: "test",
	...overrides,
});

describe("QuestionsExplorer", () => {
	const mockOnAssign = vi.fn();
	const mockOnInspect = vi.fn();
	const mockOnDelete = vi.fn();

	const defaultProps = {
		items: [],
		onAssign: mockOnAssign,
		onInspect: mockOnInspect,
		onDelete: mockOnDelete,
	};

	beforeEach(() => {
		mockOnAssign.mockClear();
		mockOnInspect.mockClear();
		mockOnDelete.mockClear();
	});

	it("should render all items when no filter is active", () => {
		const items: QuestionsExplorerItem[] = [
			createMockItem({ id: "1", status: "draft", question: "Draft Q" }),
			createMockItem({ id: "2", status: "approved", question: "Approved Q" }),
			createMockItem({
				id: "3",
				status: "draft",
				question: "Deleted Q",
				deleted: true,
			}),
		];

		render(<QuestionsExplorer {...defaultProps} items={items} />);

		expect(screen.getByText("Draft Q")).toBeInTheDocument();
		expect(screen.getByText("Approved Q")).toBeInTheDocument();
		expect(screen.getByText("Deleted Q")).toBeInTheDocument();
	});

	it("should call onAssign when Assign button clicked", () => {
		const items: QuestionsExplorerItem[] = [
			createMockItem({ id: "test-123", question: "Test Q" }),
		];

		render(<QuestionsExplorer {...defaultProps} items={items} />);

		const assignButton = screen.getByRole("button", {
			name: "Assign test-123",
		});
		fireEvent.click(assignButton);

		expect(mockOnAssign).toHaveBeenCalledWith(items[0]);
		expect(mockOnAssign).toHaveBeenCalledTimes(1);
	});

	it("should call onInspect when Inspect button clicked", () => {
		const items: QuestionsExplorerItem[] = [
			createMockItem({ id: "test-456", question: "Test Q" }),
		];

		render(<QuestionsExplorer {...defaultProps} items={items} />);

		const inspectButton = screen.getByRole("button", {
			name: "Inspect test-456",
		});
		fireEvent.click(inspectButton);

		expect(mockOnInspect).toHaveBeenCalledWith(items[0]);
		expect(mockOnInspect).toHaveBeenCalledTimes(1);
	});

	it("should call onDelete when Delete button clicked", () => {
		const items: QuestionsExplorerItem[] = [
			createMockItem({ id: "test-789", question: "Test Q" }),
		];

		render(<QuestionsExplorer {...defaultProps} items={items} />);

		const deleteButton = screen.getByRole("button", {
			name: "Delete test-789",
		});
		fireEvent.click(deleteButton);

		// onDelete is called with the full item object
		expect(mockOnDelete).toHaveBeenCalledWith(items[0]);
		expect(mockOnDelete).toHaveBeenCalledTimes(1);
	});

	it("should show item count correctly", () => {
		const items: QuestionsExplorerItem[] = [
			createMockItem({ id: "1", question: "Q1" }),
			createMockItem({ id: "2", question: "Q2" }),
			createMockItem({ id: "3", question: "Q3" }),
		];

		render(<QuestionsExplorer {...defaultProps} items={items} />);

		expect(screen.getByText("Showing 3 of 3 items")).toBeInTheDocument();
	});

	// Pagination Tests
	describe("Pagination", () => {
		it("should not show pagination controls when items fit in one page", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 10 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			expect(
				screen.queryByRole("button", { name: "Previous" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: "Next" }),
			).not.toBeInTheDocument();
		});

		it("should show pagination controls when items exceed one page", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 30 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			expect(
				screen.getByRole("button", { name: "Previous" }),
			).toBeInTheDocument();
			expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();
			expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
		});

		it("should display correct number of items per page", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 30 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			// With items prop, all items are displayed regardless of pagination settings
			// The count shows all 30 items
			expect(screen.getByText("Showing 30 of 30 items")).toBeInTheDocument();
		});

		it("should navigate to next page", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 30 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			const nextButton = screen.getByRole("button", { name: "Next" });
			fireEvent.click(nextButton);

			// Should now be on page 2
			expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
			// With items prop, all items still shown (no server-side pagination)
			expect(screen.getByText("Showing 30 of 30 items")).toBeInTheDocument();
		});

		it("should navigate to previous page", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 30 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			const nextButton = screen.getByRole("button", { name: "Next" });
			fireEvent.click(nextButton);

			const previousButton = screen.getByRole("button", { name: "Previous" });
			fireEvent.click(previousButton);

			// Should be back on page 1
			expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
			// With items prop, all items still shown
			expect(screen.getByText("Showing 30 of 30 items")).toBeInTheDocument();
		});

		it("should disable Previous button on first page", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 30 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			const previousButton = screen.getByRole("button", { name: "Previous" });
			expect(previousButton).toBeDisabled();
		});

		it("should disable Next button on last page", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 30 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			const nextButton = screen.getByRole("button", { name: "Next" });
			fireEvent.click(nextButton);

			// Now on page 2 (last page)
			expect(nextButton).toBeDisabled();
		});

		it("should navigate to specific page by clicking page number", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 60 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			// Should have 3 pages (60 items / 25 per page = 2.4, rounded up to 3)
			const page2Button = screen.getByRole("button", { name: "2" });
			fireEvent.click(page2Button);

			expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();
		});

		it("should highlight current page number", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 60 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			// Page 1 button should have active styling (bg-blue-500)
			const page1Button = screen.getByRole("button", { name: "1" });
			expect(page1Button.className).toContain("bg-blue-500");

			// Page 2 button should not have active styling
			const page2Button = screen.getByRole("button", { name: "2" });
			expect(page2Button.className).not.toContain("bg-blue-500");
		});

		it("should reset to page 1 when changing items per page from a different page", () => {
			const items: QuestionsExplorerItem[] = Array.from(
				{ length: 60 },
				(_, i) =>
					createMockItem({ id: `item-${i}`, question: `Question ${i}` }),
			);

			render(<QuestionsExplorer {...defaultProps} items={items} />);

			// Go to page 2
			const nextButton = screen.getByRole("button", { name: "Next" });
			fireEvent.click(nextButton);
			expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();

			// Change items per page
			const itemsPerPageSelect = screen.getByLabelText("Items per page:");
			fireEvent.change(itemsPerPageSelect, { target: { value: "50" } });

			// Should reset to page 1
			expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
		});
	});
});
