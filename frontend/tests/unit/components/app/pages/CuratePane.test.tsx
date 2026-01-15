import { fireEvent, render, screen } from "@testing-library/react";
import CuratePane from "../../../../../src/components/app/pages/CuratePane";
import type { AgentGenerationResult } from "../../../../../src/hooks/useGroundTruth";
import type { GroundTruthItem } from "../../../../../src/models/groundTruth";

const item: GroundTruthItem = {
	id: "1",
	question: "What is this software?",
	answer: "",
	references: [],
	status: "draft",
	providerId: "json",
	tags: [],
};

describe("CuratePane", () => {
	// DISABLED: UI now always uses multi-turn mode, so traditional Q/A fields don't exist
	it.skip("calls field updates and actions", () => {
		const onUpdateQuestion = vi.fn();
		const onUpdateAnswer = vi.fn();
		const onUpdateComment = vi.fn();
		const onUpdateTags = vi.fn();
		const onGenerateAgentTurn = vi.fn(
			async (): Promise<AgentGenerationResult> => ({
				ok: true as const,
				messageIndex: 0,
			}),
		);
		const onSaveDraft = vi.fn();
		const onApprove = vi.fn();
		const onSkip = vi.fn();
		const onDelete = vi.fn();
		const onRestore = vi.fn();

		render(
			<CuratePane
				current={item}
				canApprove={true}
				saving={false}
				onDuplicate={vi.fn()}
				onUpdateQuestion={onUpdateQuestion}
				onUpdateAnswer={onUpdateAnswer}
			onUpdateComment={onUpdateComment}
			onUpdateTags={onUpdateTags}
			onUpdateHistory={vi.fn()}
			onDeleteTurn={vi.fn()}
				onGenerateAgentTurn={onGenerateAgentTurn}
				onSaveDraft={onSaveDraft}
				onApprove={onApprove}
				onSkip={onSkip}
				onDelete={onDelete}
				onRestore={onRestore}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		const textareas = screen.getAllByRole("textbox");
		// First textarea is the Question field
		fireEvent.change(textareas[0], { target: { value: "New Q" } });
		expect(onUpdateQuestion).toHaveBeenCalled();

		// Comments is the third textarea after Answer and before buttons
		fireEvent.change(textareas[2], { target: { value: "Note" } });
		expect(onUpdateComment).toHaveBeenCalled();

		fireEvent.click(screen.getByRole("button", { name: /Save Draft/i }));
		expect(onSaveDraft).toHaveBeenCalled();

		fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
		expect(onApprove).toHaveBeenCalled();

		fireEvent.click(screen.getByRole("button", { name: /^Skip$/i }));
		expect(onSkip).toHaveBeenCalled();
	});

	it("disables Approve when deleted", () => {
		render(
		<CuratePane
			current={{ ...item, deleted: true }}
			canApprove={true}
			saving={false}
			onDuplicate={vi.fn()}
			onUpdateQuestion={vi.fn()}
			onUpdateAnswer={vi.fn()}
		onUpdateComment={vi.fn()}
		onUpdateTags={vi.fn()}
		onUpdateHistory={vi.fn()}
		onDeleteTurn={vi.fn()}
			onGenerateAgentTurn={async (): Promise<AgentGenerationResult> => ({
				ok: true as const,
				messageIndex: 0,
			})}
			onSaveDraft={vi.fn()}
				onApprove={vi.fn()}
				onSkip={vi.fn()}
				onDelete={vi.fn()}
				onRestore={vi.fn()}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		expect(screen.getByRole("button", { name: /Approve/i })).toBeDisabled();
	});

	// DISABLED: UI now always defaults to multi-turn mode
	it.skip("defaults to single-turn mode for items without history", () => {
		render(
			<CuratePane
				current={item}
				canApprove={true}
				saving={false}
				onDuplicate={vi.fn()}
				onUpdateQuestion={vi.fn()}
				onUpdateAnswer={vi.fn()}
			onUpdateComment={vi.fn()}
			onUpdateTags={vi.fn()}
			onUpdateHistory={vi.fn()}
			onDeleteTurn={vi.fn()}
				onGenerateAgentTurn={async (): Promise<AgentGenerationResult> => ({
					ok: true as const,
					messageIndex: 0,
				})}
				onSaveDraft={vi.fn()}
				onApprove={vi.fn()}
				onSkip={vi.fn()}
				onDelete={vi.fn()}
				onRestore={vi.fn()}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		// Should be in single-turn mode, showing traditional Question/Answer fields
		expect(screen.getByLabelText("Question")).toBeInTheDocument();
		expect(screen.getByLabelText("Answer")).toBeInTheDocument();
		// Multi-turn editor should not be present
		expect(screen.queryByText(/Conversation History/i)).not.toBeInTheDocument();
	});

	it("switches to multi-turn mode for items with history", () => {
		const itemWithHistory: GroundTruthItem = {
			...item,
			history: [
				{ role: "user", content: "What is this software?" },
				{ role: "agent", content: "It is a CAD software." },
			],
		};

		render(
			<CuratePane
				current={itemWithHistory}
				canApprove={true}
				saving={false}
				onDuplicate={vi.fn()}
				onUpdateQuestion={vi.fn()}
				onUpdateAnswer={vi.fn()}
				onUpdateComment={vi.fn()}
				onUpdateTags={vi.fn()}
				onUpdateHistory={vi.fn()}
				onDeleteTurn={vi.fn()}
				onGenerateAgentTurn={async (): Promise<AgentGenerationResult> => ({
					ok: true as const,
					messageIndex: 0,
				})}
				onSaveDraft={vi.fn()}
				onApprove={vi.fn()}
				onSkip={vi.fn()}
				onDelete={vi.fn()}
				onRestore={vi.fn()}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		// Should be in multi-turn mode, showing conversation history
		expect(screen.getByText(/Conversation History/i)).toBeInTheDocument();
		// Traditional Q/A fields should not be present
		expect(screen.queryByLabelText("Question")).not.toBeInTheDocument();
		expect(screen.queryByLabelText("Answer")).not.toBeInTheDocument();
	});

	// DISABLED: UI now always stays in multi-turn mode
	it.skip("switches from multi-turn to single-turn when selecting item without history", () => {
		const itemWithHistory: GroundTruthItem = {
			...item,
			id: "2",
			history: [
				{ role: "user", content: "What is this software?" },
				{ role: "agent", content: "It is a CAD software." },
			],
		};

		const { rerender } = render(
			<CuratePane
				current={itemWithHistory}
				canApprove={true}
				saving={false}
				onDuplicate={vi.fn()}
				onUpdateQuestion={vi.fn()}
				onUpdateAnswer={vi.fn()}
				onUpdateComment={vi.fn()}
				onUpdateTags={vi.fn()}
				onUpdateHistory={vi.fn()}
				onDeleteTurn={vi.fn()}
				onGenerateAgentTurn={async (): Promise<AgentGenerationResult> => ({
					ok: true as const,
					messageIndex: 0,
				})}
				onSaveDraft={vi.fn()}
				onApprove={vi.fn()}
				onSkip={vi.fn()}
				onDelete={vi.fn()}
				onRestore={vi.fn()}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		// Initially in multi-turn mode
		expect(screen.getByText(/Conversation History/i)).toBeInTheDocument();

		// Switch to item without history
		const itemWithoutHistory: GroundTruthItem = {
			...item,
			id: "3",
		};

		rerender(
			<CuratePane
				current={itemWithoutHistory}
				canApprove={true}
				saving={false}
				onDuplicate={vi.fn()}
				onUpdateQuestion={vi.fn()}
				onUpdateAnswer={vi.fn()}
				onUpdateComment={vi.fn()}
				onUpdateTags={vi.fn()}
				onUpdateHistory={vi.fn()}
				onDeleteTurn={vi.fn()}
				onGenerateAgentTurn={async (): Promise<AgentGenerationResult> => ({
					ok: true as const,
					messageIndex: 0,
				})}
				onSaveDraft={vi.fn()}
				onApprove={vi.fn()}
				onSkip={vi.fn()}
				onDelete={vi.fn()}
				onRestore={vi.fn()}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		// Should now be in single-turn mode
		expect(screen.queryByText(/Conversation History/i)).not.toBeInTheDocument();
		expect(screen.getByLabelText("Question")).toBeInTheDocument();
		expect(screen.getByLabelText("Answer")).toBeInTheDocument();
	});
});
