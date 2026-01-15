import type { GroundTruthItem, Reference } from "../models/groundTruth";
// import { DEMO_JSON, createDemoProvider } from "../models/demoData";
import { nowIso, randId } from "../models/utils";
import { refsApprovalReady } from "../models/validators";

export function runSelfTests() {
	// Reference gating tests
	const baseRef = (over: Partial<Reference> = {}): Reference => ({
		id: randId("r"),
		url: "https://x",
		visitedAt: nowIso(),
		keyParagraph: "",
		...over,
	});
	const mk = (refs: Reference[]): GroundTruthItem => ({
		id: "T",
		question: "q",
		answer: "a",
		references: refs,
		status: "draft",
		providerId: "json",
	});

	console.assert(
		refsApprovalReady(mk([])),
		"Ref Test 0 failed (empty refs should be allowed)",
	);
	console.assert(
		refsApprovalReady(mk([baseRef(), baseRef()])),
		"Ref Test 1 failed",
	);
	console.assert(
		refsApprovalReady(mk([baseRef()])),
		"Ref Test 2 failed (refs without keyParagraph should be allowed)",
	);
	console.assert(
		refsApprovalReady(mk([baseRef({ keyParagraph: "short text" })])),
		"Ref Test 3 failed (keyParagraph of any length should be allowed)",
	);
	const longKP = "x".repeat(41);
	console.assert(
		refsApprovalReady(mk([baseRef({ keyParagraph: longKP })])),
		"Ref Test 4 failed",
	);
	const unvisited = baseRef({
		keyParagraph: longKP,
		visitedAt: null,
	});
	console.assert(
		!refsApprovalReady(mk([unvisited])),
		"Ref Test 5 failed (unvisited refs should not be allowed)",
	);

	// Versioning tests removed – version is no longer used for bumping.
}
