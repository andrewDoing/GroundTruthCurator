import { Lock, X } from "lucide-react";
import { useTagDescription } from "../../hooks/useTagGlossary";
import { cn } from "../../models/utils";

type TagChipProps = {
	tag: string;
	isComputed?: boolean;
	onRemove?: () => void;
	className?: string;
};

export default function TagChip({
	tag,
	isComputed,
	onRemove,
	className,
}: TagChipProps) {
	const description = useTagDescription(tag);

	const baseClasses =
		"inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium relative group";

	const colorClasses = isComputed
		? "bg-slate-100 text-slate-600 border border-slate-200"
		: "bg-violet-100 text-violet-800";

	return (
		<span
			className={cn(baseClasses, colorClasses, className)}
			title={description}
		>
			{isComputed && <Lock className="h-3 w-3 text-slate-400" />}
			{tag}
			{onRemove && !isComputed && (
				<button
					type="button"
					onClick={onRemove}
					className="ml-1 rounded-full p-0.5 hover:bg-violet-200"
					aria-label={`Remove ${tag}`}
				>
					<X className="h-3.5 w-3.5" />
				</button>
			)}
			{description && (
				<span className="invisible group-hover:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 rounded-md bg-slate-900 px-3 py-2 text-xs text-white shadow-lg z-50 pointer-events-none">
					{description}
					<span className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-900" />
				</span>
			)}
		</span>
	);
}
