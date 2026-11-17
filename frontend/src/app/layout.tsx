import type { Metadata } from "next";
import { Space_Grotesk, Geist_Mono } from "next/font/google";
import { cn } from "@/lib/utils";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "eureka | Detección Autónoma de Fricción en UX",
  description:
    "Plataforma inteligente de detección autónoma y análisis multimodal de patrones de fricción en la experiencia de usuario.",
  icons: {
    icon: [
      { url: "/brand/eureka-logo-letra.png" },
      { url: "/icon.png", type: "image/png", sizes: "512x512" },
    ],
    shortcut: "/brand/eureka-logo-letra.png",
    apple: "/apple-icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={cn(
        spaceGrotesk.variable,
        geistMono.variable,
        "h-full antialiased"
      )}
    >
      <body className="min-h-full flex flex-col bg-white text-neutral-900 font-sans selection:bg-[#818CF8]/20 selection:text-[#4F46E5]">
        {children}
      </body>
    </html>
  );
}
