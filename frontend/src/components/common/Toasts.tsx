import type { Toast } from "../../hooks/useToasts";
import { cn } from "../../models/utils";

type Props = {
	toasts: Toast[];
	onActionClick?: (id: string, action?: () => void) => void;
};

export default function Toasts({ toasts, onActionClick }: Props) {
	if (!toasts.length) return null;
	return (
		<div className="pointer-events-none fixed bottom-4 right-4 z-[60] space-y-2">
			{toasts.map((t) => (
				<div
					key={t.id}
					className={cn(
						"pointer-events-auto flex min-w-[260px] items-center justify-between gap-3 rounded-xl border bg-white px-3 py-2 shadow",
						t.kind === "success" && "border-emerald-300",
						t.kind === "error" && "border-rose-300",
						t.kind === "info" && "border-violet-300",
					)}
				>
					<div className="text-sm">{t.msg}</div>
					{t.actionLabel && t.onAction && (
						<button
							type="button"
							className="rounded-lg border border-violet-300 px-2 py-1 text-xs text-violet-700 hover:bg-violet-50"
							onClick={() => onActionClick?.(t.id, t.onAction)}
						>
							{t.actionLabel}
						</button>
					)}
				</div>
			))}
		</div>
	);
}
