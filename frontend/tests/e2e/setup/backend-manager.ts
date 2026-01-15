/// <reference types="node" />

import { type ChildProcess, spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";

export interface BackendProcess {
	pid: number;
	startedAt: number;
	process: ChildProcess;
	logFile: string;
}

export interface StartBackendOptions {
	port: number;
	cwd: string;
	env: Record<string, string | undefined>;
	logDir: string;
	pythonExecutable?: string;
	args?: string[];
}

export async function ensureDir(dir: string): Promise<void> {
	await fs.mkdir(dir, { recursive: true });
}

export async function startBackendServer(
	options: StartBackendOptions,
): Promise<BackendProcess> {
	const { port, cwd, env, logDir } = options;
	await ensureDir(logDir);

	const pythonCandidates = [
		options.pythonExecutable,
		process.env.E2E_PYTHON,
		"python3",
		"python",
	];
	const python =
		pythonCandidates.find((candidate) => candidate?.trim()) ?? "python3";
	const args = options.args ?? [
		"-m",
		"uvicorn",
		"app.main:app",
		"--host",
		"0.0.0.0",
		"--port",
		String(port),
	];

	const logFile = path.join(logDir, `backend-${Date.now()}.log`);
	const stdioCapture = createWriteStream(logFile, { flags: "a" });

	const childEnv: Record<string, string | undefined> = {
		...process.env,
		PYTHONUNBUFFERED: "1",
		...env,
	};

	const child = spawn(python, args, {
		cwd,
		env: childEnv,
		shell: false,
		stdio: ["pipe", "pipe", "pipe"],
	});

	child.stdout.pipe(stdioCapture, { end: false });
	child.stderr.pipe(stdioCapture, { end: false });

	child.once("exit", (code: number | null, signal: NodeJS.Signals | null) => {
		stdioCapture.write(
			`\n[backend exited] code=${code} signal=${signal ?? ""}\n`,
		);
		stdioCapture.end();
	});

	child.once("error", (err: Error) => {
		stdioCapture.write(`\n[backend error] ${String(err)}\n`);
	});

	return {
		pid: child.pid ?? -1,
		startedAt: Date.now(),
		process: child,
		logFile,
	};
}

export async function waitForBackendHealth(
	url: string,
	timeoutMs = 90_000,
	pollMs = 1_000,
): Promise<void> {
	const deadline = Date.now() + timeoutMs;
	let lastError: unknown;
	while (Date.now() < deadline) {
		try {
			const res = await fetch(url, { method: "GET" });
			if (res.ok) return;
			lastError = new Error(`HTTP ${res.status}`);
		} catch (err) {
			lastError = err;
		}
		await new Promise((resolve) => setTimeout(resolve, pollMs));
	}
	throw new Error(
		`Timed out waiting for backend health at ${url}. Last error: ${String(lastError)}`,
	);
}

export async function stopBackendServer(
	proc: BackendProcess,
	timeoutMs = 15_000,
): Promise<void> {
	const { process: child } = proc;
	if (child.exitCode !== null || child.signalCode) return;

	child.kill("SIGTERM");

	const finished = new Promise<void>((resolve) => {
		child.once("exit", () => resolve());
		child.once("close", () => resolve());
	});

	const timeout = new Promise<void>((resolve) =>
		setTimeout(resolve, timeoutMs),
	);
	await Promise.race([finished, timeout]);

	if (child.exitCode === null && !child.signalCode) {
		child.kill("SIGKILL");
	}
}

export async function writeStateFile<T>(
	filePath: string,
	data: T,
): Promise<void> {
	await ensureDir(path.dirname(filePath));
	await fs.writeFile(filePath, JSON.stringify(data, null, 2), "utf8");
}

export async function readStateFile<T>(
	filePath: string,
): Promise<T | undefined> {
	try {
		const buf = await fs.readFile(filePath, "utf8");
		return JSON.parse(buf) as T;
	} catch (err) {
		if ((err as { code?: string }).code === "ENOENT") return undefined;
		throw err;
	}
}

export async function removeFile(filePath: string): Promise<void> {
	try {
		await fs.unlink(filePath);
	} catch (err) {
		if ((err as { code?: string }).code === "ENOENT") return;
		throw err;
	}
}
