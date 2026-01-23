import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect, useState } from "react";
import CuratePane from "../../../../../src/components/app/pages/CuratePane";
import type { AgentGenerationResult } from "../../../../../src/hooks/useGroundTruth";
import type { GroundTruthItem } from "../../../../../src/models/groundTruth";

function Wrapper({ initial }: { initial: GroundTruthItem | null }) {
	const [current, setCurrent] = useState<GroundTruthItem | null>(null);
	useEffect(() => {
		const t = setTimeout(() => setCurrent(initial), 0);
		return () => clearTimeout(t);
	}, [initial]);
	return (
		<CuratePane
			current={current}
			canApprove={true}
			saving={false}
			onDuplicate={() => {}}
			onUpdateQuestion={() => {}}
			onUpdateAnswer={() => {}}
			onUpdateComment={() => {}}
			onUpdateTags={() => {}}
			onUpdateHistory={() => {}}
			onGenerateAgentTurn={async (): Promise<AgentGenerationResult> => ({
				ok: true as const,
				messageIndex: 0,
			})}
			onSaveDraft={() => {}}
			onApprove={() => {}}
			onSkip={() => {}}
			onDelete={() => {}}
			onRestore={() => {}}
			onDeleteTurn={() => {}}
			onUpdateReference={() => {}}
			onRemoveReference={() => {}}
			onOpenReference={() => {}}
			onAddReferences={() => {}}
		/>
	);
}

const baseItem: GroundTruthItem = {
	id: "test-1",
	question: "Existing question",
	answer: "",
	history: [{ role: "user", content: "Existing question" }],
	comment: "",
	references: [],
	status: "draft",
	providerId: "json",
	tags: [],
};

describe("CuratePane autofocus", () => {
	// NOTE: Autofocus tests are skipped because in multi-turn mode, turns are not editable by default
	// The question is displayed as markdown, not in a textarea, so autofocus doesn't apply
	// These tests were written for single-turn mode which has been disabled
	it.skip("focuses question textarea after current loads", async () => {
		render(<Wrapper initial={baseItem} />);
		// First textbox is the Question field
		const question = await screen.findAllByRole("textbox").then((xs) => xs[0]);
		await waitFor(() => expect(question).toHaveFocus());
	});

	it.skip("does not steal focus if input already focused", async () => {
		render(
			<div>
				<input aria-label="Decoy" />
				<Wrapper initial={baseItem} />
			</div>,
		);
		const decoy = screen.getByLabelText("Decoy");
		decoy.focus();
		fireEvent.focus(decoy);
		// Wait for current to load
		const question = await screen.findAllByRole("textbox").then((xs) => xs[1]); // second textbox because of decoy input
		expect(decoy).toHaveFocus();
		expect(question).not.toHaveFocus();
	});

	it.skip("places caret at end of existing question", async () => {
		render(<Wrapper initial={baseItem} />);
		const question = (await screen.findAllByRole("textbox")).at(
			0,
		) as HTMLTextAreaElement;
		const len = baseItem.question.length;
		// selectionStart/End should be at end (wait for effect timing)
		await waitFor(() => {
			expect(question.selectionStart).toBe(len);
			expect(question.selectionEnd).toBe(len);
		});
	});
});
