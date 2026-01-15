import { useCallback, useRef } from "react";
import type { GroundTruthItem, Reference } from "../models/groundTruth";
import { dedupeReferences } from "../models/gtHelpers";
import { nowIso } from "../models/utils";

type UndoRegistrar = (undo: () => void, timeoutMs: number) => void;

type ReferencesEditorApi = {
	updateReference: (refId: string, patch: Partial<Reference>) => void;
	addReferences: (refs: Reference[]) => void;
	removeReferenceWithUndo: (
		refId: string,
		onUndoRegister: UndoRegistrar,
	) => void;
	openReference: (ref: Reference) => void;
	associateReferenceWithTurn: (refId: string, messageIndex: number) => void;
};

export function useReferencesEditor(options: {
	setCurrent: React.Dispatch<React.SetStateAction<GroundTruthItem | null>>;
}): ReferencesEditorApi {
	const { setCurrent } = options;
	const undoTimer = useRef<number | null>(null);

	const updateReference = useCallback(
		(refId: string, patch: Partial<Reference>) => {
			setCurrent((prev) => {
				if (!prev) return prev;
				return {
					...prev,
					references: prev.references.map((r) =>
						r.id === refId ? { ...r, ...patch } : r,
					),
				};
			});
		},
		[setCurrent],
	);

	const addReferences = useCallback(
		(chosen: Reference[]) => {
			setCurrent((prev) => {
				if (!prev) return prev;
				return {
					...prev,
					references: dedupeReferences(prev.references, chosen),
				};
			});
		},
		[setCurrent],
	);

	const removeReferenceWithUndo = useCallback(
		(refId: string, onUndoRegister: UndoRegistrar) => {
			setCurrent((prev) => {
				if (!prev) return prev;
				const idx = prev.references.findIndex((r) => r.id === refId);
				if (idx < 0) return prev;
				const ref = prev.references[idx];
				const nextRefs = prev.references.filter((_, i) => i !== idx);
				const doUndo = () => {
					setCurrent((p2) => {
						if (!p2) return p2;
						const present = p2.references.some((r) => r.id === ref.id);
						if (present) return p2;
						const arr = [...p2.references];
						const insertAt = Math.min(idx, arr.length);
						arr.splice(insertAt, 0, ref);
						return { ...p2, references: arr };
					});
					if (undoTimer.current) window.clearTimeout(undoTimer.current);
				};
				onUndoRegister(doUndo, 8000);
				if (undoTimer.current) window.clearTimeout(undoTimer.current);
				undoTimer.current = window.setTimeout(
					() => {},
					8000,
				) as unknown as number;
				return { ...prev, references: nextRefs };
			});
		},
		[setCurrent],
	);

	const openReference = useCallback(
		(ref: Reference) => {
			updateReference(ref.id, { visitedAt: nowIso() });
		},
		[updateReference],
	);

	const associateReferenceWithTurn = useCallback(
		(refId: string, messageIndex: number) => {
			updateReference(refId, { messageIndex });
		},
		[updateReference],
	);

	return {
		updateReference,
		addReferences,
		removeReferenceWithUndo,
		openReference,
		associateReferenceWithTurn,
	};
}
