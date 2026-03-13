import { expect, type Page, test } from "@playwright/test";
import {
	datasetNameForRun,
	itemIdForDataset,
	openExplorerAndFilter,
	seedDeterministicItem,
} from "./helpers";

const TOOL_NAME = "search_docs";

async function editTurn(page: Page, index: number, nextContent: string) {
	const turn = page.locator(`[data-turn-index="${index}"]`).first();
	await turn.getByRole("button", { name: "Edit" }).click();
	await turn.locator("textarea").fill(nextContent);
	await turn.getByRole("button", { name: "Save" }).click();
	await expect(turn).toContainText(nextContent);
}

async function setToolCallDecision(page: Page, label: RegExp) {
	const relevanceGroup = page
		.getByRole("radiogroup", {
			name: "Tool call relevance",
		})
		.first();
	await relevanceGroup.getByRole("button", { name: label }).click();
}

test("curator flow persists edits and shows approved item in Explorer", async ({
	page,
}) => {
	const datasetName = datasetNameForRun();
	const itemId = itemIdForDataset(datasetName);
	const editedUserMessage = "Edited user message from the first Playwright E2E";
	const editedAgentMessage =
		"Edited agent response persisted through the real backend";
	const editedComment = "Persisted curator note from Playwright E2E";

	await seedDeterministicItem(datasetName, itemId, TOOL_NAME);

	await page.goto("/");
	await expect(page.getByText("Ground Truth Curator")).toBeVisible();

	await openExplorerAndFilter(page, datasetName, itemId);
	await expect(
		page.getByRole("button", { name: `Assign ${itemId}` }),
	).toBeVisible();

	await page.getByRole("button", { name: `Assign ${itemId}` }).click();
	await expect(page.locator('[data-turn-index="0"]').first()).toContainText(
		"Original seeded user message",
	);

	await editTurn(page, 0, editedUserMessage);
	await editTurn(page, 1, editedAgentMessage);

	await page
		.getByRole("button", { name: `Toggle tool call ${TOOL_NAME}` })
		.first()
		.click();
	await setToolCallDecision(page, /Not needed/);
	await setToolCallDecision(page, /Optional/);
	await setToolCallDecision(page, /Required/);
	await expect(
		page.getByRole("button", { name: /Required/ }).first(),
	).toHaveAttribute("aria-pressed", "true");

	await page.getByRole("textbox", { name: "Comments" }).fill(editedComment);
	await page.getByRole("button", { name: "Save Draft" }).click();
	await expect(page.getByText(`Saved ${itemId} – draft`)).toBeVisible();

	await page.reload();
	await page.getByRole("option", { name: new RegExp(itemId) }).click();
	await expect(page.locator('[data-turn-index="0"]').first()).toContainText(
		editedUserMessage,
	);
	await expect(page.locator('[data-turn-index="1"]').first()).toContainText(
		editedAgentMessage,
	);

	await page
		.getByRole("button", { name: `Toggle tool call ${TOOL_NAME}` })
		.first()
		.click();
	await expect(
		page.getByRole("button", { name: /Required/ }).first(),
	).toHaveAttribute("aria-pressed", "true");
	await expect(page.getByRole("textbox", { name: "Comments" })).toHaveValue(
		editedComment,
	);

	await page.getByRole("button", { name: "Approve" }).click();
	await expect(page.getByText(`Saved ${itemId} – approved`)).toBeVisible();

	await openExplorerAndFilter(page, datasetName, itemId, "approved");
	const approvedRow = page
		.locator("tbody tr")
		.filter({ hasText: itemId })
		.first();
	await expect(approvedRow).toContainText("approved");
});
