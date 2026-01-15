/// <reference types="node" />

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { readStateFile } from "./backend-manager";
import type { QuestionsExplorerBlueprint } from "./test-data";

export interface EnvMap {
	[key: string]: string;
}

export interface SeededItem {
	id: string;
	datasetName: string;
	bucket: string;
	status: string;
	tags: string[];
	references: number;
	reviewedAt?: string | null;
}

export interface IntegrationState {
	runId: string;
	backend: {
		port: number;
		url: string;
		pid: number;
		logFile: string;
	};
	cosmosDbName: string;
	tags: string[];
	blueprint: QuestionsExplorerBlueprint;
	seeded: SeededItem[];
	devUserId: string;
}

const FILE_DIR = path.dirname(fileURLToPath(import.meta.url));

export const INTEGRATION_STATE_FILE = path.resolve(
	FILE_DIR,
	"../.integration-state.json",
);

export async function parseEnvFile(filePath: string): Promise<EnvMap> {
	const buf = await fs.readFile(filePath, "utf8").catch((err) => {
		if ((err as { code?: string }).code === "ENOENT") return "";
		throw err;
	});
	const res: EnvMap = {};
	for (const line of buf.split(/\r?\n/)) {
		const trimmed = line.trim();
		if (!trimmed || trimmed.startsWith("#")) continue;
		const eq = trimmed.indexOf("=");
		if (eq <= 0) continue;
		const key = trimmed.slice(0, eq).trim();
		const raw = trimmed.slice(eq + 1);
		const value = raw.replace(/^"|"$/g, "");
		res[key] = value;
	}
	return res;
}

export function mergeEnv(base: EnvMap, overrides: EnvMap): EnvMap {
	return { ...base, ...overrides };
}

export function toProcessEnv(env: EnvMap): Record<string, string | undefined> {
	return Object.fromEntries(Object.entries(env).map(([k, v]) => [k, v]));
}

async function request(
	method: "GET" | "POST" | "DELETE",
	url: string,
	body?: unknown,
	headers?: Record<string, string>,
): Promise<Response> {
	const init: RequestInit = {
		method,
		headers: {
			"Content-Type": "application/json",
			Accept: "application/json",
			...headers,
		},
	};
	if (body !== undefined) init.body = JSON.stringify(body);
	const res = await fetch(url, init);
	if (!res.ok) {
		const text = await res.text().catch(() => "");
		throw new Error(
			`HTTP ${res.status} ${res.statusText} for ${url}${text ? ` - ${text}` : ""}`,
		);
	}
	return res;
}

export async function apiPost<T>(
	baseUrl: string,
	pathName: string,
	body: unknown,
	devUser?: string,
): Promise<T> {
	const res = await request(
		"POST",
		`${baseUrl}${pathName}`,
		body,
		buildHeaders(devUser),
	);
	return (await res.json().catch(() => ({}))) as T;
}

export async function apiGet<T>(
	baseUrl: string,
	pathName: string,
	devUser?: string,
): Promise<T> {
	const res = await request(
		"GET",
		`${baseUrl}${pathName}`,
		undefined,
		buildHeaders(devUser),
	);
	return (await res.json().catch(() => ({}))) as T;
}

export async function apiDelete(
	baseUrl: string,
	pathName: string,
	devUser?: string,
): Promise<void> {
	await request(
		"DELETE",
		`${baseUrl}${pathName}`,
		undefined,
		buildHeaders(devUser),
	);
}

function buildHeaders(devUser?: string): Record<string, string> {
	const headers: Record<string, string> = {};
	if (devUser) headers["X-User-Id"] = devUser;
	return headers;
}

export function isIntegrationTest(): boolean {
	return process.env.PLAYWRIGHT_INTEGRATION === "1";
}

export async function loadIntegrationState(): Promise<
	IntegrationState | undefined
> {
	return readStateFile<IntegrationState>(INTEGRATION_STATE_FILE);
}

export async function waitForApiReady(
	url: string,
	timeoutMs = 60_000,
): Promise<void> {
	const deadline = Date.now() + timeoutMs;
	let lastError: unknown;
	while (Date.now() < deadline) {
		try {
			const res = await fetch(`${url}/healthz`);
			if (res.ok) return;
			lastError = new Error(`HTTP ${res.status}`);
		} catch (err) {
			lastError = err;
		}
		await new Promise((resolve) => setTimeout(resolve, 1_000));
	}
	throw new Error(
		`Backend not ready at ${url}/healthz. Last error: ${String(lastError)}`,
	);
}
