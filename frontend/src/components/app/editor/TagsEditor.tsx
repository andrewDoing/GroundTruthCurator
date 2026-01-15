import { Lock, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import useTags from "../../../hooks/useTags";
import { cn } from "../../../models/utils";

export default function TagsEditor({
	selected,
	computedTags,
	onChange,
	className,
	title = "Tags",
}: {
	selected: string[];
	computedTags?: string[];
	onChange: (tags: string[]) => void;
	className?: string;
	title?: string;
}) {
	const { allTags, loading, error, ensureTag, filter } = useTags();
	const [q, setQ] = useState("");
	const [open, setOpen] = useState(false);
	const inputRef = useRef<HTMLInputElement | null>(null);
	const [showInvalid, setShowInvalid] = useState(false);

	function isValidTag(raw: string) {
		const t = (raw || "").trim();
		// Require "group:value" with non-empty group and value, no additional colons
		return /^[^:]+:[^:]+$/.test(t);
	}

	// Active option index for keyboard navigation (-1 means create/new when present)
	const [activeIndex, setActiveIndex] = useState<number>(-1);

	const suggestions = useMemo(() => {
		const base = filter(q).filter((t) => !selected.includes(t));
		// prioritize prefix matches
		const pref = base.filter((t) =>
			t.toLowerCase().startsWith(q.toLowerCase()),
		);
		const rest = base.filter(
			(t) => !t.toLowerCase().startsWith(q.toLowerCase()),
		);
		return [...pref, ...rest].slice(0, 8);
	}, [filter, q, selected]);

	function add(tag: string) {
		const t = tag.trim();
		if (!t) return;
		const isNew = !allTags.includes(t);
		if (isNew && !isValidTag(t)) {
			// Surface validation error only when attempting to create a new tag
			setShowInvalid(true);
			setOpen(true);
			inputRef.current?.focus();
			return;
		}
		if (isNew) ensureTag(t); // local optimistic create
		onChange([...(selected || []), t]);
		setQ("");
		setOpen(false);
		inputRef.current?.focus();
	}
	function remove(tag: string) {
		// Confirm before removing a tag
		const ok = window.confirm(`Remove tag "${tag}"?`);
		if (!ok) return;
		onChange((selected || []).filter((t) => t !== tag));
		inputRef.current?.focus();
	}

	const createLabel =
		q && !allTags.includes(q.trim()) && isValidTag(q.trim())
			? `Create "${q.trim()}"`
			: null;

	useEffect(() => {
		if (!q) {
			setOpen(false);
			setActiveIndex(-1);
		} else {
			setOpen(true);
			// reset to first suggestion (or create) when query changes
			setActiveIndex(createLabel ? -1 : suggestions.length > 0 ? 0 : -1);
		}
		// Clear validation hint as user edits
		setShowInvalid(false);
	}, [q, createLabel, suggestions.length]);

	function getOptionId(i: number) {
		return `tags-option-${i}`;
	}

	const listboxId = "tags-listbox";

	return (
		<div className={cn("rounded-2xl border bg-white p-4 shadow-sm", className)}>
			<div className="mb-2 flex items-center gap-3">
				<div className="text-sm font-medium">{title}</div>
				<span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
					Optional
				</span>
			</div>
			<p className="mb-2 text-xs text-slate-500">
				Tags must use group:value format (example: source:email)
			</p>

			{/* Computed Tags - Read-only display */}
			{computedTags && computedTags.length > 0 && (
				<div className="mb-3">
					<div className="mb-1 text-xs text-slate-500 flex items-center gap-1">
						<Lock className="h-3 w-3" />
						Auto-generated
					</div>
					<div className="flex flex-wrap gap-2">
						{computedTags.map((t) => (
							<span
								key={t}
								className="inline-flex items-center gap-1 rounded-full bg-slate-100 border border-slate-200 px-3 py-1 text-sm text-slate-600"
							>
								<Lock className="h-3 w-3 text-slate-400" />
								{t}
							</span>
						))}
					</div>
				</div>
			)}

			{/* Manual Tags - Editable */}
			<div className="flex flex-wrap gap-2 mb-2">
				{(selected || []).map((t) => (
					<span
						key={t}
						className="inline-flex items-center gap-1 rounded-full border bg-violet-50 px-3 py-1 text-sm"
					>
						{t}
						<button
							type="button"
							onClick={() => remove(t)}
							className="ml-1 rounded-full p-0.5 text-slate-600 hover:bg-violet-100"
							aria-label={`Remove ${t}`}
						>
							<X className="h-3.5 w-3.5" />
						</button>
					</span>
				))}
			</div>
			<div className="relative">
				<input
					ref={inputRef}
					type="text"
					value={q}
					onChange={(e) => {
						setQ(e.target.value);
					}}
					role="combobox"
					aria-expanded={open}
					aria-controls={open ? listboxId : undefined}
					aria-invalid={showInvalid || undefined}
					onKeyDown={(e) => {
						if (e.key === "ArrowDown") {
							e.preventDefault();
							if (!open) {
								setOpen(true);
								return;
							}
							const max = suggestions.length - 1;
							const hasCreate = !!createLabel;
							let next = activeIndex + 1;
							if (hasCreate) {
								next = Math.min(next, max);
							} else {
								next = Math.max(0, Math.min(next, max));
							}
							setActiveIndex(next);
							return;
						}
						if (e.key === "ArrowUp") {
							e.preventDefault();
							if (!open) {
								setOpen(true);
								return;
							}
							const hasCreate = !!createLabel;
							const min = hasCreate ? -1 : 0;
							const next = Math.max(activeIndex - 1, min);
							setActiveIndex(next);
							return;
						}
						if (e.key === "Enter") {
							e.preventDefault();
							if (!q.trim() && activeIndex < 0) return;
							if (activeIndex === -1 && createLabel) {
								add(q.trim());
								return;
							}
							if (activeIndex >= 0 && activeIndex < suggestions.length) {
								add(suggestions[activeIndex]);
								return;
							}
							if (q.trim()) add(q.trim());
							return;
						}
						if (e.key === "Escape") {
							setOpen(false);
							setActiveIndex(-1);
							return;
						}
						// Note: Backspace should NOT remove tags implicitly
					}}
					aria-autocomplete="list"
					aria-activedescendant={
						open && activeIndex >= 0 ? getOptionId(activeIndex) : undefined
					}
					className={cn(
						"w-full rounded-xl border p-2 text-sm focus:outline-none",
						showInvalid
							? "border-red-300 focus:ring-2 focus:ring-red-300"
							: "focus:ring-2 focus:ring-violet-300",
					)}
					placeholder={
						loading
							? "Loading tags…"
							: error
								? "Tags unavailable"
								: "Add a tag (group:value)"
					}
					disabled={!!error}
				/>
				{showInvalid && (
					<p className="mt-1 text-xs text-red-600">
						Invalid format. Use group:value (e.g., source:email)
					</p>
				)}
				{open && (suggestions.length > 0 || createLabel) && (
					<div
						id={listboxId}
						role="listbox"
						className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-xl border bg-white p-1 shadow-lg"
					>
						{createLabel && (
							<button
								type="button"
								onClick={() => add(q.trim())}
								className={cn(
									"block w-full truncate rounded-lg px-2 py-1.5 text-left text-sm hover:bg-violet-50",
									activeIndex === -1 && "bg-violet-50",
								)}
								role="option"
								aria-selected={activeIndex === -1}
							>
								{createLabel}
							</button>
						)}
						{suggestions.map((s, i) => (
							<button
								type="button"
								key={s}
								onClick={() => add(s)}
								id={getOptionId(i)}
								role="option"
								aria-selected={activeIndex === i}
								className={cn(
									"block w-full truncate rounded-lg px-2 py-1.5 text-left text-sm hover:bg-violet-50",
									activeIndex === i && "bg-violet-50",
								)}
							>
								{s}
							</button>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
