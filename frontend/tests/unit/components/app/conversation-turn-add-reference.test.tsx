import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ConversationTurn from "../../../../src/components/app/editor/ConversationTurn";
import type { ConversationTurn as ConversationTurnType } from "../../../../src/models/groundTruth";

describe("ConversationTurn - Add Reference Button", () => {
	const mockAgentTurn: ConversationTurnType = {
		role: "agent",
		content: "This is an agent response",
		expectedBehavior: ["generation:answer"],
	};

	const mockUserTurn: ConversationTurnType = {
		role: "user",
		content: "This is a user question",
	};

	it("renders Add reference button for agent turn with no references", () => {
		const mockOnViewReferences = vi.fn();
		
		render(
			<ConversationTurn
				turn={mockAgentTurn}
				index={1}
				isLast={false}
				onUpdate={vi.fn()}
				onUpdateExpectedBehavior={vi.fn()}
				onDelete={vi.fn()}
				onRegenerate={vi.fn()}
				canEdit={true}
				isGenerating={false}
				referenceCount={0}
				onViewReferences={mockOnViewReferences}
			/>,
		);

		const addButton = screen.getByRole("button", { name: /add reference/i });
		expect(addButton).toBeInTheDocument();
		expect(addButton).toHaveTextContent("Add reference");
	});

	it("does not render Add reference button for user turns", () => {
		render(
			<ConversationTurn
				turn={mockUserTurn}
				index={0}
				isLast={false}
				onUpdate={vi.fn()}
				onDelete={vi.fn()}
				canEdit={true}
				isGenerating={false}
				referenceCount={0}
				onViewReferences={vi.fn()}
			/>,
		);

		const addButton = screen.queryByRole("button", { name: /add reference/i });
		expect(addButton).not.toBeInTheDocument();
	});

	it("does not render Add reference button when references exist", () => {
		const mockOnViewReferences = vi.fn();
		
		render(
			<ConversationTurn
				turn={mockAgentTurn}
				index={1}
				isLast={false}
				onUpdate={vi.fn()}
				onUpdateExpectedBehavior={vi.fn()}
				onDelete={vi.fn()}
				onRegenerate={vi.fn()}
				canEdit={true}
				isGenerating={false}
				referenceCount={2}
				onViewReferences={mockOnViewReferences}
			/>,
		);

		const addButton = screen.queryByRole("button", { name: /add reference/i });
		expect(addButton).not.toBeInTheDocument();
		
		// Should show the count button instead
		const countButton = screen.getByRole("button", { name: /2 references/i });
		expect(countButton).toBeInTheDocument();
	});

	it("calls onViewReferences when Add reference clicked", () => {
		const mockOnViewReferences = vi.fn();
		
		render(
			<ConversationTurn
				turn={mockAgentTurn}
				index={1}
				isLast={false}
				onUpdate={vi.fn()}
				onUpdateExpectedBehavior={vi.fn()}
				onDelete={vi.fn()}
				onRegenerate={vi.fn()}
				canEdit={true}
				isGenerating={false}
				referenceCount={0}
				onViewReferences={mockOnViewReferences}
			/>,
		);

		const addButton = screen.getByRole("button", { name: /add reference/i });
		fireEvent.click(addButton);
		
		expect(mockOnViewReferences).toHaveBeenCalledTimes(1);
	});

	it("Add reference button uses same styling as count button", () => {
		const mockOnViewReferences = vi.fn();
		
		const { rerender } = render(
			<ConversationTurn
				turn={mockAgentTurn}
				index={1}
				isLast={false}
				onUpdate={vi.fn()}
				onUpdateExpectedBehavior={vi.fn()}
				onDelete={vi.fn()}
				onRegenerate={vi.fn()}
				canEdit={true}
				isGenerating={false}
				referenceCount={0}
				onViewReferences={mockOnViewReferences}
			/>,
		);

		const addButton = screen.getByRole("button", { name: /add reference/i });
		const addButtonClasses = addButton.className;
		
		// Rerender with references to get the count button
		rerender(
			<ConversationTurn
				turn={mockAgentTurn}
				index={1}
				isLast={false}
				onUpdate={vi.fn()}
				onUpdateExpectedBehavior={vi.fn()}
				onDelete={vi.fn()}
				onRegenerate={vi.fn()}
				canEdit={true}
				isGenerating={false}
				referenceCount={1}
				onViewReferences={mockOnViewReferences}
			/>,
		);

		const countButton = screen.getByRole("button", { name: /1 reference$/i });
		const countButtonClasses = countButton.className;
		
		// Both buttons should have the same styling classes
		expect(addButtonClasses).toBe(countButtonClasses);
	});
});
