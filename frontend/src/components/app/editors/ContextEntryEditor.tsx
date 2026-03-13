/**
 * ContextEntryEditor — editable list of context entries (key-value pairs).
 *
 * Supports inline editing, adding new entries, and removing entries.
 * Changes propagate through onUpdate callback which receives the full
 * updated entries array.
 *
 * Phase 3 Step 3.3.
 */

import { Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ContextEntry } from "../../../models/groundTruth";
import { cn } from "../../../models/utils";

function ContextEntryRow({
	entry,
	onUpdateKey,
	onUpdateValue,
	onRemove,
}: {
	entry: ContextEntry;
	onUpdateKey: (key: string) => void;
	onUpdateValue: (value: unknown) => void;
	onRemove: () => void;
}) {
	const [editing, setEditing] = useState(false);
	const textareaRef = useRef<HTMLTextAreaElement>(null);
	const [localValue, setLocalValue] = useState(() =>
		typeof entry.value === "string"
			? entry.value
			: JSON.stringify(entry.value, null, 2),
	);

	// Focus textarea when entering edit mode
	useEffect(() => {
		if (editing) textareaRef.current?.focus();
	}, [editing]);

	const commitValue = useCallback(() => {
		setEditing(false);
		// Try to parse as JSON; fall back to string
		let parsed: unknown;
		try {
			parsed = JSON.parse(localValue);
		} catch {
			parsed = localValue;
		}
		onUpdateValue(parsed);
	}, [localValue, onUpdateValue]);

	return (
		<div className="group rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
			<div className="flex items-start gap-2">
				<input
					type="text"
					aria-label="Context entry key"
					className="font-mono text-xs text-slate-600 bg-transparent border-b border-dashed border-slate-300 focus:border-violet-400 focus:outline-none px-0.5 py-0 flex-shrink-0 w-32"
					value={entry.key}
					onChange={(e) => onUpdateKey(e.target.value)}
				/>
				<span className="text-xs text-slate-400 flex-shrink-0">:</span>

				{editing ? (
					<textarea
						ref={textareaRef}
						aria-label="Context entry value"
						className="flex-1 min-h-[3rem] resize-y rounded-md border border-slate-300 bg-white p-2 text-xs text-slate-700 font-mono focus:outline-none focus:ring-1 focus:ring-violet-300"
						value={localValue}
						onChange={(e) => setLocalValue(e.target.value)}
						onBlur={commitValue}
						onKeyDown={(e) => {
							if (e.key === "Enter" && !e.shiftKey) {
								e.preventDefault();
								commitValue();
							}
						}}
					/>
				) : (
					<button
						type="button"
						className={cn(
							"flex-1 text-left text-xs text-slate-700 break-all rounded px-1 py-0.5",
							"hover:bg-violet-50 hover:text-violet-800 cursor-text transition-colors",
						)}
						onClick={() => {
							setLocalValue(
								typeof entry.value === "string"
									? entry.value
									: JSON.stringify(entry.value, null, 2),
							);
							setEditing(true);
						}}
						title="Click to edit"
					>
						{typeof entry.value === "object"
							? JSON.stringify(entry.value)
							: String(entry.value ?? "")}
					</button>
				)}

				<button
					type="button"
					onClick={onRemove}
					className="flex-shrink-0 rounded p-1 text-slate-400 opacity-0 group-hover:opacity-100 hover:bg-rose-50 hover:text-rose-600 transition-all"
					aria-label={`Remove context entry ${entry.key}`}
					title="Remove entry"
				>
					<Trash2 className="h-3.5 w-3.5" />
				</button>
			</div>
		</div>
	);
}

export default function ContextEntryEditor({
	entries,
	onUpdate,
}: {
	entries: ContextEntry[];
	onUpdate: (entries: ContextEntry[]) => void;
}) {
	const updateEntry = useCallback(
		(index: number, patch: Partial<ContextEntry>) => {
			const next = entries.map((e, i) =>
				i === index ? { ...e, ...patch } : e,
			);
			onUpdate(next);
		},
		[entries, onUpdate],
	);

	const removeEntry = useCallback(
		(index: number) => {
			onUpdate(entries.filter((_, i) => i !== index));
		},
		[entries, onUpdate],
	);

	const addEntry = useCallback(() => {
		onUpdate([...entries, { key: "", value: "" }]);
	}, [entries, onUpdate]);

	return (
		<div className="space-y-2">
			{entries.map((entry, i) => (
				<ContextEntryRow
					// biome-ignore lint/suspicious/noArrayIndexKey: entries have no stable id
					key={i}
					entry={entry}
					onUpdateKey={(key) => updateEntry(i, { key })}
					onUpdateValue={(value) => updateEntry(i, { value })}
					onRemove={() => removeEntry(i)}
				/>
			))}

			<button
				type="button"
				onClick={addEntry}
				className="flex items-center gap-1.5 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500 hover:border-violet-400 hover:text-violet-600 hover:bg-violet-50 transition-colors w-full justify-center"
			>
				<Plus className="h-3.5 w-3.5" />
				Add context entry
			</button>
		</div>
	);
}
