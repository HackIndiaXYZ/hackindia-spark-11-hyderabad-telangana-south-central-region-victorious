import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";

/*
 * `display: "swap"` keeps text painted in the fallback face while Geist loads,
 * so the workspace never flashes blank. The metric-adjacent system stack in
 * `globals.css` keeps the swap from reflowing the layout noticeably.
 */
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Project Victorious",
    template: "%s · Project Victorious",
  },
  description:
    "An AI-native Software Engineering Workspace. Specialized engineering agents " +
    "coordinate requirements, architecture, implementation, testing, and documentation " +
    "over a shared organizational memory — with full traceability and human approval.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="min-h-screen antialiased">
        {/*
          The workspace nav has eleven links on every project page. Without a way
          past it, a keyboard or screen-reader user tabs through all of them
          before reaching content on every navigation. `10_UI_UX_Plan.md` treats
          accessibility as a core requirement rather than an enhancement.
        */}
        <a
          href="#main"
          className="sr-only rounded-lg bg-accent px-4 py-2 text-sm font-medium text-canvas focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
