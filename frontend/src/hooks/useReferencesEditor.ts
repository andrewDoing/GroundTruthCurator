import { useCallback, useRef } from "react";
import type { GroundTruthItem, Reference } from "../models/groundTruth";
import {
	getItemReferences,
	withUpdatedReferences,
} from "../models/groundTruth";
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
				const refs = getItemReferences(prev);
				const updated = refs.map((r) =>
					r.id === refId ? { ...r, ...patch } : r,
				);
				return withUpdatedReferences(prev, updated);
			});
		},
		[setCurrent],
	);

	const addReferences = useCallback(
		(chosen: Reference[]) => {
			setCurrent((prev) => {
				if (!prev) return prev;
				const refs = getItemReferences(prev);
				return withUpdatedReferences(prev, dedupeReferences(refs, chosen));
			});
		},
		[setCurrent],
	);

	const removeReferenceWithUndo = useCallback(
		(refId: string, onUndoRegister: UndoRegistrar) => {
			setCurrent((prev) => {
				if (!prev) return prev;
				const refs = getItemReferences(prev);
				const idx = refs.findIndex((r) => r.id === refId);
				if (idx < 0) return prev;
				const ref = refs[idx];
				const nextRefs = refs.filter((_, i) => i !== idx);
				const doUndo = () => {
					setCurrent((p2) => {
						if (!p2) return p2;
						const currentRefs = getItemReferences(p2);
						const present = currentRefs.some((r) => r.id === ref.id);
						if (present) return p2;
						const arr = [...currentRefs];
						const insertAt = Math.min(idx, arr.length);
						arr.splice(insertAt, 0, ref);
						return withUpdatedReferences(p2, arr);
					});
					if (undoTimer.current) window.clearTimeout(undoTimer.current);
				};
				onUndoRegister(doUndo, 8000);
				if (undoTimer.current) window.clearTimeout(undoTimer.current);
				undoTimer.current = window.setTimeout(
					() => {},
					8000,
				) as unknown as number;
				return withUpdatedReferences(prev, nextRefs);
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
