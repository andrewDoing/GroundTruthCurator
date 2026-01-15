import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
	test: {
		globals: true,
		environment: "jsdom",
		setupFiles: ["./vitest.setup.ts"],
		include: ["tests/unit/**/*.{test,spec}.{ts,tsx}"],
		exclude: [...configDefaults.exclude, "e2e", "tests/e2e"],
		reporters: ["default", "junit"],
		outputFile: {
			junit: "./junit-results.xml"
		}
	},
});
