import { CircleAlert, Clipboard, RefreshCw } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { GroundTruthItem } from "../../models/groundTruth";
import { cn } from "../../models/utils";

type Props = {
	items: GroundTruthItem[];
	selectedId: string | null;
	onSelect: (id: string) => void;
	onRefresh: () => void;
	className?: string;
	// Optional: identify which item has unsaved changes
	hasUnsavedId?: (id: string) => boolean;
	// Optional: trigger self-serve action
	onSelfServe?: () => void;
	selfServeBusy?: boolean;
	// Optional: notify when a copy to clipboard succeeds
	onCopied?: (kind: "id" | "dataset" | "path", value: string) => void;
};

export default function QueueSidebar({
	items,
	selectedId,
	onSelect,
	onRefresh,
	className,
	hasUnsavedId,
	onSelfServe,
	selfServeBusy,
	onCopied,
}: Props) {
	const labelId = useId();
	const containerRef = useRef<HTMLDivElement | null>(null);
	const [hoverIndex, setHoverIndex] = useState<number>(-1);
	const ids = useMemo(() => items.map((it) => it.id), [items]);
	useEffect(() => {
		const idx = selectedId ? ids.indexOf(selectedId) : -1;
		setHoverIndex(idx >= 0 ? idx : 0);
	}, [selectedId, ids]);

	function getItemId(i: number) {
		return `queue-item-${ids[i]}`;
	}

	async function copy(text: string) {
		try {
			await navigator.clipboard.writeText(text);
			return true;
		} catch {
			return false;
		}
	}

	function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
		if (e.key === "ArrowDown") {
			e.preventDefault();
			const next = Math.min(
				hoverIndex < 0 ? 0 : hoverIndex + 1,
				items.length - 1,
			);
			setHoverIndex(next);
			document
				.getElementById(getItemId(next))
				?.scrollIntoView({ block: "nearest" });
		} else if (e.key === "ArrowUp") {
			e.preventDefault();
			const next = Math.max(hoverIndex < 0 ? 0 : hoverIndex - 1, 0);
			setHoverIndex(next);
			document
				.getElementById(getItemId(next))
				?.scrollIntoView({ block: "nearest" });
		} else if (e.key === "Enter") {
			e.preventDefault();
			if (hoverIndex >= 0 && hoverIndex < items.length)
				onSelect(items[hoverIndex].id);
		}
	}
	return (
		<aside
			className={cn(
				"self-start h-[calc(100vh-5.5rem)] rounded-2xl border bg-white p-3 shadow-sm flex flex-col overflow-hidden",
				className,
			)}
		>
			<div className="mb-2 flex items-center justify-between">
				<div className="font-medium" id={labelId}>
					Queue
				</div>
				<button
					type="button"
					onClick={onRefresh}
					className="inline-flex items-center gap-2 rounded-lg border px-2 py-1 text-xs hover:bg-violet-50"
				>
					<RefreshCw className="h-3.5 w-3.5" /> Refresh
				</button>
			</div>
			<div
				ref={containerRef}
				tabIndex={0}
				onKeyDown={onKeyDown}
				role="listbox"
				aria-labelledby={labelId}
				aria-activedescendant={
					hoverIndex >= 0 ? getItemId(hoverIndex) : undefined
				}
				className="flex-1 min-h-0 overflow-auto pr-1 focus:outline-none"
			>
				<div className="space-y-2">
					{items.map((it, i) => (
						<div
							key={it.id}
							onClick={() => {
								onSelect(it.id);
								containerRef.current?.focus();
							}}
							onKeyDown={(e) => {
								if (e.key === "Enter" || e.key === " ") {
									e.preventDefault();
									onSelect(it.id);
									containerRef.current?.focus();
								}
							}}
							role="option"
							aria-selected={selectedId === it.id}
							tabIndex={0}
							className={cn(
								"w-full rounded-xl border p-3 text-left hover:bg-violet-50",
								selectedId === it.id && "border-violet-400 bg-violet-50",
								i === hoverIndex &&
									selectedId !== it.id &&
									"ring-2 ring-violet-300",
								it.deleted && "opacity-60",
							)}
							id={getItemId(i)}
						>
							<div className="flex items-center justify-between gap-2">
								<div className="font-medium line-clamp-1 flex items-center gap-2">
									{/* ID text (not interactive) */}
									<span className="select-text">{it.id}</span>
									{/* Optional dataset pill with click-to-copy */}
									{(() => {
										const ds = it.datasetName;
										if (!ds) return null;
										return (
											<span className="inline-flex items-center gap-1">
												<span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-800">
													{ds}
												</span>
											</span>
										);
									})()}

									{/* Single copy button: dataset/bucket/id (omits missing parts) */}
									<button
										type="button"
										onClick={(e) => {
											e.stopPropagation();
											const parts = [it.datasetName, it.bucket, it.id].filter(
												(v): v is string => Boolean(v),
											);
											const path = parts.join("/");
											copy(path).then((ok) => {
												if (ok) onCopied?.("path", path);
											});
										}}
										className="inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs text-slate-700 hover:bg-slate-100"
										aria-label="Copy dataset/bucket/id"
										title="Copy dataset/bucket/id"
									>
										<Clipboard className="h-3.5 w-3.5" />
									</button>
									{it.deleted && (
										<span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-900">
											deleted
										</span>
									)}
									{hasUnsavedId?.(it.id) && (
										<span
											className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-900"
											title="Unsaved changes"
										>
											<CircleAlert className="h-3.5 w-3.5" /> unsaved
										</span>
									)}
								</div>
								<span
									className={cn(
										"rounded-full px-2 py-0.5 text-xs",
										it.status === "draft" && "bg-amber-100 text-amber-900",
										it.status === "approved" &&
											"bg-emerald-100 text-emerald-900",
										it.status === "skipped" && "bg-slate-200 text-slate-800",
									)}
								>
									{it.status}
								</span>
							</div>
							<div
								className="truncate text-xs text-slate-600"
								title={it.question}
							>
								{it.question}
							</div>
						</div>
					))}
				</div>
			</div>
			{onSelfServe && (
				<div className="pt-2 mt-2 border-t">
					<button
						type="button"
						onClick={onSelfServe}
						disabled={selfServeBusy}
						className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-violet-300 bg-violet-600 px-3 py-2 text-sm text-white shadow hover:bg-violet-700 disabled:opacity-50"
						title="Request more items to curate"
					>
						{selfServeBusy ? "Requesting…" : "Request More (Self‑serve)"}
					</button>
				</div>
			)}
		</aside>
	);
}
