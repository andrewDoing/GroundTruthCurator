import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TagsModal from "../../../../../src/components/app/editor/TagsModal";
import TurnReferencesModal from "../../../../../src/components/app/editor/TurnReferencesModal";

function ensureModalRoot() {
	let el = document.getElementById("modal-root");
	if (!el) {
		el = document.createElement("div");
		el.id = "modal-root";
		document.body.appendChild(el);
	}
	return el;
}

describe("Editor modals portal into #modal-root", () => {
	beforeEach(() => {
		ensureModalRoot().innerHTML = "";
	});

	it("renders TagsModal inside #modal-root", () => {
		render(
			<TagsModal
				isOpen={true}
				onClose={vi.fn()}
				tags={[]}
				computedTags={[]}
				availableTags={[]}
				onUpdateTags={vi.fn()}
			/>,
		);

		const modalRoot = ensureModalRoot();
		expect(modalRoot).toContainElement(
			screen.getByRole("dialog", { name: /manage tags/i }),
		);
	});

	it("renders TurnReferencesModal inside #modal-root", () => {
		render(
			<TurnReferencesModal
				isOpen={true}
				onClose={vi.fn()}
				messageIndex={1}
				references={[]}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		const modalRoot = ensureModalRoot();
		expect(modalRoot).toContainElement(
			screen.getByRole("dialog", { name: /references for turn/i }),
		);
	});
});
