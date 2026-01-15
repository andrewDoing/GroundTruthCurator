import type { GroundTruthItem } from "../../../models/groundTruth";
import { cn } from "../../../models/utils";

export default function QuestionsList({
	items,
	onDelete,
	onRestore,
	onOpen,
}: {
	items: GroundTruthItem[];
	onDelete: (id: string) => void;
	onRestore: (id: string) => void;
	onOpen?: (id: string) => void;
}) {
	return (
		<section className="rounded-2xl border bg-white p-4 shadow-sm">
			<div className="mb-4">
				<div className="text-sm font-medium">Questions</div>
				<div className="text-xs text-slate-600">
					Scan questions and delete poor ones. Use Open to review in the editor.
				</div>
			</div>
			<div className="space-y-2">
				{items.map((it) => (
					<div
						key={it.id}
						className={cn("rounded-xl border p-3", it.deleted && "opacity-60")}
					>
						<div className="flex items-start justify-between gap-2">
							<div className="min-w-0 flex-1">
								<div className="text-xs text-slate-500">
									{it.id} •{" "}
									<span
										className={cn(
											"rounded-full px-1.5 py-0.5",
											it.status === "draft"
												? "bg-amber-100 text-amber-900"
												: "bg-emerald-100 text-emerald-900",
										)}
									>
										{it.status}
									</span>
								</div>
								<div
									className="text-sm font-medium truncate"
									title={it.question}
								>
									{it.question || "(no question)"}
								</div>
							</div>
							<div className="flex items-center gap-2 flex-none">
								{onOpen && (
									<button
										type="button"
										className="rounded-xl border px-3 py-2 text-sm hover:bg-violet-50"
										onClick={() => onOpen(it.id)}
										title="Open this item in the editor"
									>
										Open
									</button>
								)}
								{!it.deleted && (
									<button
										type="button"
										className="rounded-xl border border-rose-300 bg-rose-600 px-3 py-2 text-sm text-white shadow hover:bg-rose-700"
										onClick={() => onDelete(it.id)}
										title="Soft delete this item"
									>
										Delete
									</button>
								)}
								{it.deleted && (
									<button
										type="button"
										className="rounded-xl border border-emerald-300 bg-emerald-600 px-3 py-2 text-sm text-white shadow hover:bg-emerald-700"
										onClick={() => onRestore(it.id)}
										title="Restore this item"
									>
										Restore
									</button>
								)}
							</div>
						</div>
					</div>
				))}
			</div>
		</section>
	);
}
