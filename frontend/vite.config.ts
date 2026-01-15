import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
	plugins: [react(), tailwindcss()],
	define: {
		// Make DEMO_MODE available to the client non-prefixed
		...(() => {
			const glb = globalThis as unknown as {
				process?: { env?: Record<string, string | undefined> };
			};
			const demo = glb.process?.env?.DEMO_MODE ?? "";
			return { "import.meta.env.DEMO_MODE": JSON.stringify(demo) };
		})(),
	},
	server: {
		proxy: {
			// Forward API calls to backend in dev to avoid CORS
			"/v1": {
				target: "http://localhost:8000",
				changeOrigin: true,
				secure: false,
			},
		},
	},
});
