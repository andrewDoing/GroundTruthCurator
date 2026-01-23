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
		references: [
			{
				id: "r1",
				title: "User Guide - Account Security",
				url: "https://example.com/docs/account-security",
				snippet:
					"Click the Reset Password button in the Security tab to initiate the recovery flow.",
				visitedAt: null,
				keyParagraph: "",
			},
			{
				id: "r2",
				title: "Troubleshooting Login Issues",
				url: "https://example.com/docs/troubleshooting-login",
				snippet:
					"If you forgot your password, use the reset feature in User Settings.",
				visitedAt: null,
				keyParagraph: "",
			},
		],
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
		references: [
			{
				id: "r3",
				title: "Data Export Capabilities",
				url: "https://example.com/docs/data-export",
				snippet:
					"Supported formats include CSV for spreadsheets, JSON for web apps, and XML for legacy systems.",
				visitedAt: null,
				keyParagraph: "",
			},
		],
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
