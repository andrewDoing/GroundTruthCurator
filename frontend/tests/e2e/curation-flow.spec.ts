import { expect, type Page, test } from "@playwright/test";

const TOOL_NAME = "search_docs";
const BUCKET = "00000000-0000-0000-0000-000000000000";
const DEV_USER =
	process.env.PLAYWRIGHT_DEV_USER ?? "playwright-e2e@example.com";
const BACKEND_URL =
	process.env.PLAYWRIGHT_BACKEND_URL ?? "http://127.0.0.1:8010";

function datasetNameForRun() {
	return `playwright-e2e-${Date.now()}`;
}

function itemIdForDataset(datasetName: string) {
	return `${datasetName}-item`;
}

async function seedDeterministicItem(datasetName: string, itemId: string) {
	const response = await fetch(`${BACKEND_URL}/v1/ground-truths`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"X-User-Id": DEV_USER,
		},
		body: JSON.stringify([
			{
				id: itemId,
				datasetName,
				bucket: BUCKET,
				status: "draft",
				comment: "Seeded by Playwright E2E",
				history: [
					{
						role: "user",
						msg: "Original seeded user message",
					},
					{
						role: "assistant",
						msg: "Original seeded agent response",
					},
				],
				toolCalls: [
					{
						id: "tool-call-1",
						name: TOOL_NAME,
						callType: "tool",
						stepNumber: 1,
						arguments: {
							query: "ground truth curator",
						},
						response: {
							hits: ["Ground Truth Curator docs"],
						},
					},
				],
				expectedTools: {
					required: [],
					optional: [{ name: TOOL_NAME }],
					notNeeded: [],
				},
				metadata: {
					seededBy: "playwright",
				},
				scenarioId: "playwright-real-e2e",
			},
		]),
	});

	if (!response.ok) {
		throw new Error(`Seed failed: ${response.status} ${await response.text()}`);
	}

	const body = await response.json();
	expect(body.imported).toBe(1);
	expect(body.uuids).toContain(itemId);
}

async function openExplorerAndFilter(
	page: Page,
	datasetName: string,
	itemId: string,
	status: "all" | "approved" = "all",
) {
	await page.getByRole("button", { name: "Explorer" }).click();
	await expect(page.getByText("Explore all ground truths")).toBeVisible();

	const datasetSelect = page.getByRole("combobox");
	await expect
		.poll(async () => {
			const options = await datasetSelect.locator("option").allTextContents();
			return options.includes(datasetName);
		})
		.toBe(true);
	await datasetSelect.selectOption(datasetName);

	await page.getByPlaceholder("Enter item ID to search...").fill(itemId);

	if (status === "approved") {
		await page.getByRole("button", { name: "Approved" }).click();
	}

	await page.getByRole("button", { name: "Apply Filters" }).click();
}

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

	await seedDeterministicItem(datasetName, itemId);

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
