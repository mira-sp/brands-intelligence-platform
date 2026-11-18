// frontend/app/layout.tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "../src/globals.css";

const ui = Geist({ variable: "--font-ui", subsets: ["latin"] });
const code = Geist_Mono({ variable: "--font-code", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Visibility",
  description: "What AI assistants tell your customers about your brand",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${ui.variable} ${code.variable} antialiased`}>{children}</body>
    </html>
  );
}
