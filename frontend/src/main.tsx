import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import ErrorBoundary from "./components/common/ErrorBoundary";
import { initTelemetry, logEvent } from "./services/telemetry";

const rootElement = document.getElementById("root");
if (!rootElement) {
	throw new Error("Failed to find the root element");
}

// Kick off telemetry early
void initTelemetry().then(() => {
	logEvent("gtc.app_start");
});

createRoot(rootElement).render(
	<StrictMode>
		<ErrorBoundary>
			<App />
		</ErrorBoundary>
	</StrictMode>,
);
