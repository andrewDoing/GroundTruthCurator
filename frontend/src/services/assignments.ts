import { client } from "../api/client";
import type { components } from "../api/generated";

type GroundTruthItemOut = components["schemas"]["GroundTruthItem-Output"];
type SelfServeResponse = components["schemas"]["SelfServeResponse"];

// Request new assignments (self-serve). Returns payload with assigned items and counts.
export async function requestAssignmentsSelfServe(
	limit: number,
): Promise<SelfServeResponse> {
	const { data, error } = await client.POST("/v1/assignments/self-serve", {
		body: { limit } as Record<string, unknown>,
	});
	if (error) throw error;
	return data as SelfServeResponse;
}

// List items currently assigned to the caller.
export async function getMyAssignments(): Promise<GroundTruthItemOut[]> {
	const { data, error } = await client.GET("/v1/assignments/my");
	if (error) throw error;
	return (data as unknown as GroundTruthItemOut[]) ?? [];
}

// Update an assigned item. Requires dataset, bucket, and item id. If-Match etag supported.
export async function updateAssignedGroundTruth(
	dataset: string,
	bucket: string,
	itemId: string,
	patch: Partial<GroundTruthItemOut>,
	etag?: string | null,
): Promise<GroundTruthItemOut> {
	const { data, error } = await client.PUT(
		"/v1/assignments/{dataset}/{bucket}/{item_id}",
		{
			params: { path: { dataset, bucket, item_id: itemId } },
			headers: etag ? { "If-Match": etag } : undefined,
			body: patch as unknown as Record<string, unknown>,
		},
	);
	if (error) throw error;
	return data as unknown as GroundTruthItemOut;
}

// Duplicate an item as a rephrase. Creates a new draft with tag `rephrase:{originalId}`
// and assigns it to the requesting user. Returns the created item payload.
export async function duplicateItem(
	dataset: string,
	bucket: string,
	itemId: string,
): Promise<GroundTruthItemOut> {
	const { data, error } = await client.POST(
		"/v1/assignments/{dataset}/{bucket}/{item_id}/duplicate",
		{
			params: { path: { dataset, bucket, item_id: itemId } },
		},
	);
	if (error) throw error;
	return data as unknown as GroundTruthItemOut;
}

// Assign a specific ground truth item to the current user.
// Sets the item status to draft and creates an assignment document.
export async function assignItem(
	dataset: string,
	bucket: string,
	itemId: string,
): Promise<GroundTruthItemOut> {
	const { data, error } = await client.POST(
		"/v1/assignments/{dataset}/{bucket}/{item_id}/assign",
		{
			params: { path: { dataset, bucket, item_id: itemId } },
		},
	);
	if (error) throw error;
	return data as unknown as GroundTruthItemOut;
}
