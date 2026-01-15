import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import CuratePane from "../../../../src/components/app/pages/CuratePane";
import type { AgentGenerationResult } from "../../../../src/hooks/useGroundTruth";
import QueueSidebar from "../../../../src/components/app/QueueSidebar";
import type { GroundTruthItem } from "../../../../src/models/groundTruth";

// Minimal harness to exercise interactions between the sidebar and the editor
function MiniCurateApp() {
	const [sidebarOpen, setSidebarOpen] = useState(true);
	const [view, setView] = useState<"curate" | "questions">("curate");
	const [items, setItems] = useState<GroundTruthItem[]>([
		{
			id: "1",
			question: "Q-1",
			answer: "",
			history: [
				{ role: "user", content: "Q-1" },
			],
			references: [],
			status: "draft",
			providerId: "json",
			tags: [],
		},
		{
			id: "2",
			question: "Q-2",
			answer: "",
			history: [
				{ role: "user", content: "Q-2" },
			],
			references: [],
			status: "draft",
			providerId: "json",
			tags: [],
		},
	]);
	const [selectedId, setSelectedId] = useState<string>(items[0].id);
	const [unsaved, setUnsaved] = useState(false);

	const current = items.find((i) => i.id === selectedId) ?? null;

	return (
		<div>
			<div>
				<button type="button" onClick={() => setSidebarOpen((v) => !v)}>
					{sidebarOpen ? "Hide Sidebar" : "Show Sidebar"}
				</button>
				<button
					type="button"
					onClick={() =>
						setView((v) => (v === "curate" ? "questions" : "curate"))
					}
				>
					{view === "curate" ? "Questions View" : "Back to Curation"}
				</button>
			</div>
			{view === "curate" ? (
				<div
					style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 16 }}
				>
					{sidebarOpen && (
						<QueueSidebar
							items={items}
							selectedId={selectedId}
							onSelect={(id) => {
								setSelectedId(id);
								setUnsaved(false);
							}}
							onRefresh={() => void 0}
							hasUnsavedId={(id) => unsaved && id === selectedId}
						/>
					)}
					<CuratePane
						current={current}
						canApprove={true}
						saving={false}
						onDuplicate={() => void 0}
						onUpdateQuestion={(q) => {
							setItems((arr) =>
								arr.map((i) =>
									i.id === selectedId ? { ...i, question: q } : i,
								),
							);
							setUnsaved(true);
						}}
						onUpdateComment={() => void 0}
						onUpdateAnswer={() => void 0}
						onUpdateTags={() => void 0}
						onUpdateHistory={(history) => {
							setItems((arr) =>
								arr.map((i) =>
									i.id === selectedId ? { ...i, history, question: history[0]?.content || "" } : i,
								),
							);
							setUnsaved(true);
						}}
						onDeleteTurn={() => void 0}
						onGenerateAgentTurn={async (): Promise<AgentGenerationResult> => ({
							ok: true as const,
							messageIndex: 0,
						})}
						onSaveDraft={() => void 0}
						onApprove={() => void 0}
						onSkip={() => void 0}
						onDelete={() => void 0}
						onRestore={() => void 0}
						onUpdateReference={() => void 0}
						onRemoveReference={() => void 0}
						onOpenReference={() => void 0}
						onAddReferences={() => void 0}
					/>
				</div>
			) : (
				<section>
					<h2>Questions Review</h2>
				</section>
			)}
		</div>
	);
}

describe("Curate layout interactions (unit)", () => {
	it("should toggle sidebar visibility", () => {
		render(<MiniCurateApp />);
		// Sidebar initially shown
		expect(screen.getByText(/Queue/i)).toBeInTheDocument();
		fireEvent.click(screen.getByRole("button", { name: /Hide Sidebar/i }));
		expect(screen.queryByText(/Queue/i)).not.toBeInTheDocument();
		fireEvent.click(screen.getByRole("button", { name: /Show Sidebar/i }));
		expect(screen.getByText(/Queue/i)).toBeInTheDocument();
	});

	it("should switch between curate and questions views", () => {
		render(<MiniCurateApp />);
		fireEvent.click(screen.getByRole("button", { name: /Questions View/i }));
		expect(
			screen.getByRole("button", { name: /Back to Curation/i }),
		).toBeInTheDocument();
		fireEvent.click(screen.getByRole("button", { name: /Back to Curation/i }));
		expect(
			screen.getByRole("button", { name: /Questions View/i }),
		).toBeInTheDocument();
	});

	it("should select queue item and show its details", () => {
		render(<MiniCurateApp />);
		// Click the second item (id "2") in the sidebar
		// QueueSidebar renders options in a listbox; each item has role="option"
		fireEvent.click(screen.getByRole("option", { name: /Q-2/ }));
		// The conversation history header should be visible
		expect(screen.getByText(/Conversation History/i)).toBeInTheDocument();
		// In multi-turn mode, verify the selected item has changed by checking sidebar state
		const selectedOption = screen.getByRole("option", { name: /Q-2/ });
		expect(selectedOption).toHaveAttribute("aria-selected", "true");
	});

	it("should edit question and show unsaved indicator", () => {
		render(<MiniCurateApp />);
		// In multi-turn mode, we need to click Edit on the first turn
		// Find the first turn's Edit button
		const editButtons = screen.getAllByRole("button", { name: /Edit/i });
		fireEvent.click(editButtons[0]);
		
		// Now find the textarea (it appears when in edit mode)
		const textarea = screen.getByPlaceholderText(/Enter user message/i);
		fireEvent.change(textarea, { target: { value: "Q-1 updated" } });
		
		// Save the edit by clicking the "Save" button within the turn (not "Save Draft")
		// Use getAllByRole and find the save button by its title or position
		const saveButtons = screen.getAllByRole("button", { name: /Save/i });
		// The first Save button is the turn's save button, the second is "Save Draft"
		fireEvent.click(saveButtons[0]);
		
		// Unsaved chip should appear in the sidebar for the selected item
		expect(screen.getByText(/unsaved/i)).toBeInTheDocument();
	});
});
