import type { Metadata } from "next";
import { Press_Start_2P, Poppins } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const pressStart = Press_Start_2P({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-press-start",
  display: "swap",
});

const poppins = Poppins({
  weight: ["300", "400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-poppins",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SOTA StatWorks — From Data to Decisions, Instantly",
  description:
    "AI-powered statistical decision engine that turns raw data into ranked insights and simulations — without statistical expertise. Upload a dataset, ask a question, get a decision.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${pressStart.variable} ${poppins.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-white text-[#1A1A2E]">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
