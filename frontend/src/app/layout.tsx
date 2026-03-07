import type { Metadata } from "next";
import { DM_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const sans = DM_Sans({ subsets: ["latin"], variable: "--font-dm-sans" });
const serif = Source_Serif_4({ subsets: ["latin"], variable: "--font-source-serif" });

export const metadata: Metadata = {
  title: "IRLI — Israel Research Lab Index",
  description: "LLM-powered index of graduate research labs in Israel",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable}`}>
      <body className="min-h-screen bg-cream text-navy antialiased">
        <header className="border-b border-slate-200 bg-white shadow-soft">
          <div className="mx-auto max-w-6xl px-4 py-3">
            <a href="/" className="font-serif text-xl font-semibold text-navy hover:text-accent transition-colors">
              IRLI — Israel Research Lab Index
            </a>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
