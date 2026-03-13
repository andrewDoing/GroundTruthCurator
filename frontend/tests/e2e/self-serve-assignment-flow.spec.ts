import { expect, type Page, test } from "@playwright/test";
import {
	datasetNameForRun,
	itemIdForDataset,
	seedDeterministicItem,
} from "./helpers";

function escapeRegExp(value: string) {
	return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function editTurn(page: Page, index: number, nextContent: string) {
	const turn = page.locator(`[data-turn-index="${index}"]`).first();
	await turn.getByRole("button", { name: "Edit" }).click();
	await turn.locator("textarea").fill(nextContent);
	await turn.getByRole("button", { name: "Save" }).click();
	await expect(turn).toContainText(nextContent);
}

test("self-serve assignment flow persists saved content after reload", async ({
	page,
}) => {
	const datasetName = datasetNameForRun();
	const itemId = itemIdForDataset(datasetName);
	const editedUserMessage =
		"Edited user message from the self-serve Playwright E2E";
	const editedComment = "Persisted self-serve curator note from Playwright E2E";

	await seedDeterministicItem(datasetName, itemId);
	await page.route("**/v1/config", async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				requireReferenceVisit: true,
				requireKeyParagraph: false,
				selfServeLimit: 500,
				trustedReferenceDomains: [],
			}),
		});
	});

	await page.goto("/");
	await expect(page.getByText("Ground Truth Curator")).toBeVisible();

	const queue = page.getByRole("listbox", { name: "Queue" });
	await page.getByRole("button", { name: "Request More (Self‑serve)" }).click();
	await expect(page.getByText(/Assigned \d+ item\(s\) to you\./)).toBeVisible();

	await page.getByRole("button", { name: "Refresh" }).click();
	await expect(page.getByText("Refreshed queue.")).toBeVisible();

	const queueItem = queue.getByRole("option", { name: new RegExp(itemId) });
	await expect(queueItem).toBeVisible();
	await queueItem.click();
	await expect(queueItem).toHaveAttribute("aria-selected", "true");
	await expect(page.locator('[data-turn-index="0"]').first()).toContainText(
		"Original seeded user message",
	);

	await editTurn(page, 0, editedUserMessage);
	await page.getByRole("textbox", { name: "Comments" }).fill(editedComment);
	await page.getByRole("button", { name: "Save Draft" }).click();
	await expect(
		page.getByText(new RegExp(`^Saved ${escapeRegExp(itemId)} – draft$`)),
	).toBeVisible();

	await page.reload();
	const reloadedQueueItem = page.getByRole("option", {
		name: new RegExp(`^${escapeRegExp(itemId)}\\b`),
	});
	await expect(reloadedQueueItem).toBeVisible();
	await reloadedQueueItem.click();
	await expect(reloadedQueueItem).toHaveAttribute("aria-selected", "true");
	await expect(page.locator('[data-turn-index="0"]').first()).toContainText(
		editedUserMessage,
	);
	await expect(page.getByRole("textbox", { name: "Comments" })).toHaveValue(
		editedComment,
	);
});
