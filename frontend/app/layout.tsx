import type { Metadata } from "next";
import { Sintony, Poppins } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const sintony = Sintony({
  weight: ["400", "700"],
  subsets: ["latin"],
  variable: "--font-sintony",
  display: "swap",
});

const poppins = Poppins({
  weight: ["300", "400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-poppins",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SOTA StatWorks — Từ Hồ Sơ đến Học Bổng",
  description:
    "Nền tảng dự đoán học bổng AI cho học sinh Việt Nam. Upload bảng điểm, CV, chứng chỉ — AI tự động tìm 100+ trường phù hợp và dự đoán cơ hội học bổng trong 60 giây.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="vi"
      className={`${sintony.variable} ${poppins.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-white text-[#1A1A2E]">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
