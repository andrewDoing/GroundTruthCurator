import type { GroundTruthItem } from "./groundTruth";
import type { Provider } from "./provider";
import { JsonProvider } from "./provider";

export const DEMO_JSON: GroundTruthItem[] = [
	{
		id: "GT-0001",
		providerId: "json",
		question: "How do I reset my password in the application?",
		answer:
			"To reset your password, navigate to User Settings > Security and click 'Reset Password'. You will receive an email with a link to create a new password.",
		plugins: {
			"rag-compat": {
				kind: "rag-compat",
				version: "1.0",
				data: {
					retrievals: {
						_unassociated: {
							candidates: [
								{
									url: "https://example.com/docs/account-security",
									title: "User Guide - Account Security",
									chunk:
										"Click the Reset Password button in the Security tab to initiate the recovery flow.",
								},
								{
									url: "https://example.com/docs/troubleshooting-login",
									title: "Troubleshooting Login Issues",
									chunk:
										"If you forgot your password, use the reset feature in User Settings.",
								},
							],
						},
					},
				},
			},
		},
		status: "draft",
		deleted: false,
		tags: ["account", "security", "password"],
		comment: "Example of a standard procedural question.",
		curationInstructions: `
### Curation Guidelines (Account Security)

- Ensure the answer is direct and step-by-step.
- Verify that the 'Reset Password' button location is accurately described.
- Link to the official User Guide whenever possible.
`,
	},
	{
		id: "GT-0002",
		providerId: "json",
		question: "What formats are supported for data export?",
		answer:
			"The application supports exporting data in CSV, JSON, and XML formats. You can select your preferred format from the Export dialog.",
		plugins: {
			"rag-compat": {
				kind: "rag-compat",
				version: "1.0",
				data: {
					retrievals: {
						_unassociated: {
							candidates: [
								{
									url: "https://example.com/docs/data-export",
									title: "Data Export Capabilities",
									chunk:
										"Supported formats include CSV for spreadsheets, JSON for web apps, and XML for legacy systems.",
								},
							],
						},
					},
				},
			},
		},
		status: "draft",
		deleted: false,
		tags: ["export", "data", "formats"],
		comment: undefined,
		curationInstructions: `
### Curation Guidelines (Data Export)

- List all supported formats explicitly.
- Mention where the Export dialog is located if not obvious.
`,
	},
];

export function createDemoProvider(): Provider {
	return new JsonProvider(DEMO_JSON);
}
