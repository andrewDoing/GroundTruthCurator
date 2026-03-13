import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InspectItemModal from "../../../../src/components/modals/InspectItemModal";
import { useGroundTruthCache } from "../../../../src/hooks/useGroundTruthCache";
import type { GroundTruthItem } from "../../../../src/models/groundTruth";

const serviceMocks = vi.hoisted(() => ({
	getGroundTruth: vi.fn(),
}));

vi.mock("../../../../src/services/groundTruths", () => ({
	getGroundTruth: serviceMocks.getGroundTruth,
}));

vi.mock("../../../../src/hooks/useModalKeys", () => ({
	default: vi.fn(),
}));

vi.mock("../../../../src/components/app/editor/MultiTurnEditor", () => ({
	default: ({ current }: { current: GroundTruthItem }) => (
		<div data-testid="multi-turn-editor">{current.id}</div>
	),
}));

vi.mock("../../../../src/components/common/TagChip", () => ({
	default: ({ tag, isComputed }: { tag: string; isComputed?: boolean }) => (
		<span>{isComputed ? `computed:${tag}` : `manual:${tag}`}</span>
	),
}));

function createItem(overrides: Partial<GroundTruthItem> = {}): GroundTruthItem {
	return {
		id: "item-123",
		status: "draft",
		providerId: "api",
		datasetName: "list-dataset",
		bucket: "list-bucket",
		manualTags: ["stale-manual"],
		computedTags: ["stale-computed"],
		comment: "Stale list comment",
		reviewedAt: "2026-03-01T12:00:00.000Z",
		history: [
			{ role: "user", content: "Original question", turnId: "turn-1" },
			{ role: "agent", content: "Original answer", turnId: "turn-2" },
		],
		...overrides,
	};
}

describe("InspectItemModal", () => {
	beforeEach(() => {
		serviceMocks.getGroundTruth.mockReset();
		useGroundTruthCache().clear();
	});

	it("renders fetched metadata from the refreshed item", async () => {
		const listItem = createItem();
		const fetchedItem = createItem({
			status: "approved",
			datasetName: "fresh-dataset",
			bucket: "fresh-bucket",
			manualTags: ["fresh-manual"],
			computedTags: ["fresh-computed"],
			comment: "Fresh item comment",
			reviewedAt: "2026-03-13T08:45:00.000Z",
		});
		serviceMocks.getGroundTruth.mockResolvedValue(fetchedItem);

		render(
			<InspectItemModal isOpen={true} item={listItem} onClose={vi.fn()} />,
		);

		await waitFor(() => {
			expect(screen.getByText("approved")).toBeInTheDocument();
		});

		expect(screen.getByText("fresh-dataset")).toBeInTheDocument();
		expect(screen.getByText("fresh-bucket")).toBeInTheDocument();
		expect(screen.getByText("Fresh item comment")).toBeInTheDocument();
		expect(screen.getByText("computed:fresh-computed")).toBeInTheDocument();
		expect(screen.getByText("manual:fresh-manual")).toBeInTheDocument();

		expect(screen.queryByText("Stale list comment")).not.toBeInTheDocument();
		expect(
			screen.queryByText("computed:stale-computed"),
		).not.toBeInTheDocument();
		expect(screen.queryByText("manual:stale-manual")).not.toBeInTheDocument();
	});

	it("falls back to the original item metadata when the full fetch fails", async () => {
		const listItem = createItem();
		serviceMocks.getGroundTruth.mockRejectedValue(new Error("Fetch failed"));

		render(
			<InspectItemModal isOpen={true} item={listItem} onClose={vi.fn()} />,
		);

		await waitFor(() => {
			expect(screen.getByText("Fetch failed")).toBeInTheDocument();
		});

		expect(screen.getByText("draft")).toBeInTheDocument();
		expect(screen.getByText("list-dataset")).toBeInTheDocument();
		expect(screen.getByText("list-bucket")).toBeInTheDocument();
		expect(screen.getByText("Stale list comment")).toBeInTheDocument();
		expect(screen.getByText("computed:stale-computed")).toBeInTheDocument();
		expect(screen.getByText("manual:stale-manual")).toBeInTheDocument();
		expect(screen.getByTestId("multi-turn-editor")).toHaveTextContent(
			"item-123",
		);
	});
});
