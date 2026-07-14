import { Syne, JetBrains_Mono } from "next/font/google";
import type { Metadata, Viewport } from "next";
import "./globals.css";

const display = Syne({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "700", "800"],
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "VERGE — Ten Strata Scrollytelling",
  description:
    "An interactive cinematic journey through ten unique 3D worlds. Scroll is time. Space tells the story.",
  metadataBase: new URL("https://verge.experience.local"),
  openGraph: {
    title: "VERGE",
    description: "Interactive film × digital art installation in the browser.",
    type: "website",
    images: [{ url: "/og/verge.svg", width: 1200, height: 630, alt: "VERGE" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "VERGE",
    description: "Ten floors. One continuous world. Scroll to travel.",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#020203",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${mono.variable}`}>
      <body className="min-h-screen overflow-x-hidden bg-[#020203] antialiased">
        {children}
      </body>
    </html>
  );
}
