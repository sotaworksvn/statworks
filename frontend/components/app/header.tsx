"use client";

import Image from "next/image";
import { useAppStore } from "@/lib/store";
import { SignInButton, UserButton } from "@clerk/nextjs";

interface AppHeaderProps {
  onUploadClick: () => void;
}

export function AppHeader({ onUploadClick }: AppHeaderProps) {
  const { datasetName, rowCount, isAnalyzing, user } = useAppStore();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-100 bg-white px-6">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <Image src="/logo.png" alt="SOTA StatWorks" width={120} height={35} priority />
      </div>

      {/* Dataset badge */}
      <div className="flex items-center gap-3">
        {datasetName && (
          <div className="flex items-center gap-2 rounded-full bg-[#F5F5F7] px-4 py-1.5 text-sm">
            <span
              className={`h-2 w-2 rounded-full ${
                isAnalyzing
                  ? "bg-[#F59E0B] animate-pulse"
                  : "bg-[#22C55E]"
              }`}
            />
            <span className="font-medium text-[#2D3561]">{datasetName}</span>
            <span className="text-gray-400">·</span>
            <span className="text-gray-400">{rowCount} rows</span>
          </div>
        )}
      </div>

      {/* Right section: upload + auth */}
      <div className="flex items-center gap-3">
        <button
          onClick={onUploadClick}
          className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-[#2D3561] hover:bg-[#F5F5F7] transition-colors"
        >
          {datasetName ? "Replace Dataset" : "Upload Dataset"}
        </button>

        {/* Clerk auth: UserButton shows profile when signed in, SignInButton when not */}
        {user ? (
          <UserButton
            appearance={{
              elements: {
                avatarBox: "h-8 w-8",
              },
            }}
          />
        ) : (
          <SignInButton mode="modal">
            <button className="rounded-lg bg-[#2D3561] px-4 py-2 text-sm font-medium text-white hover:bg-[#3a4578] transition-colors">
              Sign In
            </button>
          </SignInButton>
        )}
      </div>
    </header>
  );
}
