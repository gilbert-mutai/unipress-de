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
        {/* Deep-green band with the mark on white, as on unideb.hu. The gold
            underline on hover is their link treatment. */}
        <header className="sticky top-0 z-20 bg-header text-header-fg shadow-sm">
          <div className="mx-auto flex max-w-content items-center justify-between gap-4 px-6">
            <a href="/" className="flex items-center gap-3 py-2">
              <span className="flex items-center rounded-md bg-white px-2 py-1.5">
                <BrandMark />
              </span>
              <span className="font-serif text-lg font-semibold tracking-tight">UniPress DE</span>
            </a>
            <div className="flex items-center gap-1.5">
              <a
                href={`${API_BASE}/docs`}
                target="_blank"
                rel="noreferrer"
                className="hidden rounded-md px-3 py-2 text-sm font-medium text-header-fg/85 decoration-accent decoration-2 underline-offset-8 transition-colors hover:text-header-fg hover:underline sm:block"
              >
                API
              </a>
              <ThemeToggle onHeader />
            </div>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
