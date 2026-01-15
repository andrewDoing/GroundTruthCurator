import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import StatsPage from "../../../../../src/components/app/pages/StatsPage";
import type { StatsPayload } from "../../../../../src/components/app/StatsView";
import type { GroundTruthItem } from "../../../../../src/models/groundTruth";
import * as statsSvc from "../../../../../src/services/stats";

vi.mock("../../../../../src/services/stats");

describe("StatsPage", () => {
	const items: GroundTruthItem[] = [] as GroundTruthItem[];

	it("renders happy path stats", async () => {
		(
			statsSvc.getGroundTruthStats as unknown as {
				mockResolvedValue: (v: StatsPayload) => void;
			}
		).mockResolvedValue({
			total: { approved: 1, draft: 2, deleted: 3 },
			perSprint: [],
		});
		(
			statsSvc.mockGetGroundTruthStats as unknown as {
				mockResolvedValue: (v: StatsPayload) => void;
			}
		).mockResolvedValue({
			total: { approved: 9, draft: 8, deleted: 7 },
			perSprint: [],
		});

		render(<StatsPage demoMode={false} items={items} onBack={vi.fn()} />);

		expect(screen.getByText(/Loading stats/i)).toBeInTheDocument();

		await waitFor(() =>
			expect(screen.getByText(/approved/i)).toBeInTheDocument(),
		);
	});

	it("falls back to zero on error", async () => {
		(
			statsSvc.getGroundTruthStats as unknown as {
				mockRejectedValue: (e: unknown) => void;
			}
		).mockRejectedValue(new Error("boom"));

		render(<StatsPage demoMode={false} items={items} onBack={vi.fn()} />);

		await waitFor(() =>
			expect(screen.getByText(/approved/i)).toBeInTheDocument(),
		);
	});

	it("uses mock service when demoMode", async () => {
		(
			statsSvc.mockGetGroundTruthStats as unknown as {
				mockResolvedValue: (v: StatsPayload) => void;
			}
		).mockResolvedValue({
			total: { approved: 5, draft: 0, deleted: 0 },
			perSprint: [],
		});

		render(<StatsPage demoMode={true} items={items} onBack={vi.fn()} />);

		await waitFor(() =>
			expect(screen.getByText(/approved/i)).toBeInTheDocument(),
		);
	});

	it("calls onBack when Back clicked", async () => {
		(
			statsSvc.mockGetGroundTruthStats as unknown as {
				mockResolvedValue: (v: StatsPayload) => void;
			}
		).mockResolvedValue({
			total: { approved: 0, draft: 0, deleted: 0 },
			perSprint: [],
		});
		const onBack = vi.fn();

		render(<StatsPage demoMode items={items} onBack={onBack} />);

		await waitFor(() => screen.getByRole("button", { name: /Back/i }));
		fireEvent.click(screen.getByRole("button", { name: /Back/i }));
		expect(onBack).toHaveBeenCalled();
	});
});
