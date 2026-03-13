import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const env = (() => {
	const glb = globalThis as unknown as {
		process?: { env?: Record<string, string | undefined> };
	};
	return glb.process?.env ?? {};
})();

const backendProxyTarget = env.HARNESS_BACKEND_URL ?? "http://localhost:8000";

function normalizeViteBasePath(basePath: string | undefined): string {
	if (!basePath) return "/";
	const trimmed = basePath.trim();
	if (!trimmed || trimmed === "/") return "/";
	return `/${trimmed.replace(/^\/+|\/+$/g, "")}/`;
}

const appBasePath = normalizeViteBasePath(env.VITE_APP_BASE_PATH);
const apiProxyPrefixes = Array.from(
	new Set([
		"/v1",
		`${appBasePath.endsWith("/") ? appBasePath.slice(0, -1) : appBasePath}/v1`,
	]),
);
const proxy = Object.fromEntries(
	apiProxyPrefixes.map((prefix) => [
		prefix,
		{
			target: backendProxyTarget,
			changeOrigin: true,
			secure: false,
		},
	]),
);

// https://vite.dev/config/
export default defineConfig({
	base: appBasePath,
	plugins: [react(), tailwindcss()],
	define: {
		// Make DEMO_MODE available to the client non-prefixed
		"import.meta.env.DEMO_MODE": JSON.stringify(env.DEMO_MODE ?? ""),
	},
	server: {
		// Forward API calls to backend in dev to avoid CORS
		proxy,
	},
});
