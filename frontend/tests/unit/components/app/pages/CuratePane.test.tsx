import { render, screen } from "@testing-library/react";
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
	it("disables Approve when deleted", () =>
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
		));

	expect(screen.getByRole("button", { name: /Approve/i })).toBeDisabled();

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
});
