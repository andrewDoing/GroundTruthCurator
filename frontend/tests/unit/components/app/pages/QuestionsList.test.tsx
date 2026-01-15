import { fireEvent, render, screen } from "@testing-library/react";
import QuestionsList from "../../../../../src/components/app/pages/QuestionsList";
import type { GroundTruthItem } from "../../../../../src/models/groundTruth";

const mkItem = (id: string, deleted = false): GroundTruthItem => ({
	id,
	question: `Q-${id}`,
	answer: "",
	tags: [],
	status: "draft",
	providerId: "json",
	deleted,
	references: [],
});

describe("QuestionsList", () => {
	const items = [mkItem("a"), mkItem("b", true)];

	it("calls onOpen with id", () => {
		const onOpen = vi.fn();
		render(
			<QuestionsList
				items={items}
				onDelete={vi.fn()}
				onRestore={vi.fn()}
				onOpen={onOpen}
			/>,
		);
		fireEvent.click(screen.getAllByRole("button", { name: /Open/i })[0]);
		expect(onOpen).toHaveBeenCalledWith("a");
	});

	it("calls onDelete for non-deleted", () => {
		const onDelete = vi.fn();
		render(
			<QuestionsList items={items} onDelete={onDelete} onRestore={vi.fn()} />,
		);
		fireEvent.click(screen.getByRole("button", { name: /Delete/i }));
		expect(onDelete).toHaveBeenCalledWith("a");
	});

	it("calls onRestore for deleted", () => {
		const onRestore = vi.fn();
		render(
			<QuestionsList items={items} onDelete={vi.fn()} onRestore={onRestore} />,
		);
		fireEvent.click(screen.getByRole("button", { name: /Restore/i }));
		expect(onRestore).toHaveBeenCalledWith("b");
	});
});
