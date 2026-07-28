import type { Metadata } from "next";
import "@fontsource-variable/fraunces";
import "@fontsource-variable/inter";
import { BrandMark } from "./components/brand-mark";
import { ThemeToggle } from "./components/theme-toggle";
import "./globals.css";
import { API_BASE } from "./lib/api";

export const metadata: Metadata = {
  title: "UniPress DE",
  description:
    "Turn a research paper into bilingual, publication-ready communication — every claim linked to its source and audited for hallucination.",
  // Tab icon: the same University of Debrecen mark the header shows, referenced
  // from /public rather than copied to app/icon.svg so there is one logo file.
  icons: { icon: "/ud-logo.svg" },
};

// Set the theme before paint to avoid a flash.
const noFlash = `(function(){try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme:dark)').matches))document.documentElement.classList.add('dark');}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: noFlash }} />
      </head>
      <body>
        <header className="sticky top-0 z-20 border-b border-line bg-paper/80 backdrop-blur">
          <div className="mx-auto flex max-w-content items-center justify-between px-6 py-3">
            <a href="/" className="flex items-center gap-2.5">
              <BrandMark />
              <span className="font-serif text-lg font-semibold tracking-tight">UniPress DE</span>
            </a>
            <div className="flex items-center gap-3">
              <a
                href={`${API_BASE}/docs`}
                target="_blank"
                rel="noreferrer"
                className="hidden text-sm text-muted hover:text-ink sm:block"
              >
                API
              </a>
              <ThemeToggle />
            </div>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
