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

// https://vite.dev/config/
export default defineConfig({
	plugins: [react(), tailwindcss()],
	define: {
		// Make DEMO_MODE available to the client non-prefixed
		"import.meta.env.DEMO_MODE": JSON.stringify(env.DEMO_MODE ?? ""),
	},
	server: {
		proxy: {
			// Forward API calls to backend in dev to avoid CORS
			"/v1": {
				target: backendProxyTarget,
				changeOrigin: true,
				secure: false,
			},
		},
	},
});
