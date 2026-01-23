import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

describe("Modal keyboard handling", () => {
	beforeEach(() => {
		ensureModalRoot().innerHTML = "";
	});

	it("closes TurnReferencesModal on Escape key", () => {
		const onClose = vi.fn();
		render(
			<TurnReferencesModal
				isOpen={true}
				onClose={onClose}
				messageIndex={1}
				references={[]}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		fireEvent.keyDown(window, { key: "Escape" });
		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("closes TagsModal on Escape key", () => {
		const onClose = vi.fn();
		render(
			<TagsModal
				isOpen={true}
				onClose={onClose}
				tags={[]}
				computedTags={[]}
				availableTags={[]}
				onUpdateTags={vi.fn()}
			/>,
		);

		fireEvent.keyDown(window, { key: "Escape" });
		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("does not close TurnReferencesModal on Space key", () => {
		const onClose = vi.fn();
		render(
			<TurnReferencesModal
				isOpen={true}
				onClose={onClose}
				messageIndex={1}
				references={[]}
				onUpdateReference={vi.fn()}
				onRemoveReference={vi.fn()}
				onOpenReference={vi.fn()}
			/>,
		);

		fireEvent.keyDown(window, { key: " " });
		expect(onClose).not.toHaveBeenCalled();
	});

	it("does not close TagsModal on Space key", () => {
		const onClose = vi.fn();
		render(
			<TagsModal
				isOpen={true}
				onClose={onClose}
				tags={[]}
				computedTags={[]}
				availableTags={[]}
				onUpdateTags={vi.fn()}
			/>,
		);

		fireEvent.keyDown(window, { key: " " });
		expect(onClose).not.toHaveBeenCalled();
	});
});
