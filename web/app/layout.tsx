import type { Metadata } from "next";
import { Space_Grotesk } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import Footer from "@/components/Footer";

const font = Space_Grotesk({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Loan Funnel & KYC Experiment", template: "%s · Loan Funnel & KYC Experiment" },
  description:
    "Simulated-data analysis: where applicants drop out of a fictional lender's loan funnel, and whether a simpler KYC flow fixes it.",
};

// Apply the saved theme before first paint; storage may be unavailable, so guard it.
const themeScript = `try{var t=localStorage.getItem("theme");if(t==="dark"||t==="light"){document.documentElement.setAttribute("data-theme",t)}}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={font.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="font-sans antialiased">
        <a href="#main" className="no-print sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-panel focus:px-3 focus:py-2">
          Skip to content
        </a>
        <Sidebar />
        <div className="min-[900px]:ml-[300px]">
          <main id="main" className="print-full mx-auto min-w-0 max-w-cards px-4 py-10 min-[900px]:px-12">
            {children}
          </main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
