import type { Metadata } from "next";
import { IntegrationView } from "./IntegrationView";

export const metadata: Metadata = { title: "Integration for companies: Unhook" };

export default function Integration() {
  return <IntegrationView />;
}
