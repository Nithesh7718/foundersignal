import type { Metadata } from "next";
import "@/app/globals.css";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "FounderSignal — AI Operating Companion",
  description:
    "Evidence-first operating companion for founders to track commitments, decisions, and delivery.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
