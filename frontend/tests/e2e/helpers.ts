import { expect, type Page } from "@playwright/test";

const BUCKET = "00000000-0000-0000-0000-000000000000";
const DEV_USER =
	process.env.PLAYWRIGHT_DEV_USER ?? "playwright-e2e@example.com";
const BACKEND_URL =
	process.env.PLAYWRIGHT_BACKEND_URL ?? "http://127.0.0.1:8010";

export function datasetNameForRun() {
	return `playwright-e2e-${Date.now()}`;
}

export function itemIdForDataset(datasetName: string) {
	return `${datasetName}-item`;
}

export async function seedDeterministicItem(
	datasetName: string,
	itemId: string,
	toolName = "search_docs",
) {
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
						name: toolName,
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
					optional: [{ name: toolName }],
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

export async function filterExplorerResults(
	page: Page,
	datasetName: string,
	itemId: string,
	status: "all" | "approved" = "all",
) {
	await expect(page.getByText("Explore all ground truths")).toBeVisible();

	const datasetSelect = page.getByLabel("Dataset:");
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

export async function openExplorerAndFilter(
	page: Page,
	datasetName: string,
	itemId: string,
	status: "all" | "approved" = "all",
) {
	await page.getByRole("button", { name: "Explorer" }).click();
	await filterExplorerResults(page, datasetName, itemId, status);
}
