import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "SOTA StatWorks — App",
  description: "AI-powered statistical analysis and simulation interface.",
};

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white">
      {children}
    </div>
  );
}
