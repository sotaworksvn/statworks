"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { analyzeDataset } from "@/lib/api";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

const SUGGESTED_PROMPTS = [
  "What affects customer retention?",
  "What drives freedom index?",
  "Which factor has the biggest impact?",
];

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function ChatPanel() {
  const {
    fileId,
    user,
    insight,
    setInsight,
    setIsAnalyzing,
    setAnalyzeError,
    isAnalyzing,
    analyzeError,
    invalidateLocalData,
    chatMessages: messages,
    addChatMessage,
  } = useAppStore();

  const [query, setQuery] = useState("");
  const [promptsHidden, setPromptsHidden] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAnalyzing]);

  const analyzeMutation = useMutation({
    mutationFn: async (q: string) => {
      if (!fileId) throw new Error("No dataset loaded");
      return analyzeDataset(fileId, q, user?.id);
    },
    onMutate: () => {
      setIsAnalyzing(true);
      setAnalyzeError(null);
    },
    onSuccess: (data) => {
      setInsight(data);
      setIsAnalyzing(false);

      // If AI edited data, invalidate local cache so Data View re-fetches from backend
      if (data.result_type === "data_edit" && fileId) {
        invalidateLocalData(fileId);
      }

      const aiMsg = data.not_supported
        ? data.suggestion ?? "This type of question is not supported yet."
        : data.summary;
      addChatMessage({ role: "assistant", content: aiMsg });

      // Autosave to history (fire-and-forget, OUTSIDE state updater)
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      fetch(`${backendUrl}/api/history`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(user?.id ? { "x-clerk-user-id": user.id } : {}),
        },
        body: JSON.stringify({
          category: "chat",
          title: aiMsg.slice(0, 60) + (aiMsg.length > 60 ? "…" : ""),
          snapshot: { messages: [{ role: "assistant", content: aiMsg }] },
        }),
      }).catch((err) => console.warn("[history autosave] chat:", err));
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : "Analysis failed";
      setAnalyzeError(message);
      setIsAnalyzing(false);
      addChatMessage({ role: "assistant", content: `Error: ${message}` });
      toast.error(message);
    },
  });

  const handleSubmit = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      if (!fileId) {
        toast.error("Upload a dataset to start.");
        return;
      }

      // Add user message
      addChatMessage({ role: "user", content: trimmed });
      setPromptsHidden(true);
      setQuery("");

      // Trigger mutation
      analyzeMutation.mutate(trimmed);
    },
    [fileId, analyzeMutation]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(query);
    }
  };

  return (
    <section className="flex w-[35%] flex-col bg-white border-r border-gray-100">
      {/* Chat header */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-50">
        <span className="text-xs font-pixel text-[#2D3561] uppercase tracking-wider">Chat</span>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
        {messages.length === 0 && !promptsHidden && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <p className="text-gray-400 text-sm text-center">
              {fileId
                ? "Ask a question about your data"
                : "Upload a dataset to start"}
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-[#2D3561] text-white rounded-br-md"
                  : "bg-[#F5F5F7] text-[#1A1A2E] rounded-bl-md"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isAnalyzing && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-md bg-[#F5F5F7] px-4 py-2.5 text-sm text-gray-500">
              <span className="inline-flex gap-1">
                Analyzing relationships
                <span className="animate-pulse">.</span>
                <span className="animate-pulse" style={{ animationDelay: "200ms" }}>.</span>
                <span className="animate-pulse" style={{ animationDelay: "400ms" }}>.</span>
              </span>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Suggested prompts */}
      {!promptsHidden && fileId && messages.length === 0 && (
        <div className="px-5 pb-2 flex flex-wrap gap-2">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => handleSubmit(prompt)}
              className="rounded-full border border-[#2D3561]/15 bg-[#2D3561]/5 px-3 py-1.5 text-xs text-[#2D3561] font-medium hover:bg-[#2D3561]/10 transition-colors"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Input box */}
      <div className="flex gap-2 px-5 py-3 border-t border-gray-100">
        <input
          id="chat-input"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your data…"
          disabled={!fileId || isAnalyzing}
          className="flex-1 rounded-xl border border-gray-200 bg-[#F5F5F7] px-4 py-2.5 text-sm text-[#1A1A2E] placeholder:text-gray-400 outline-none focus:border-[#2D3561]/30 focus:ring-1 focus:ring-[#2D3561]/10 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        />
        <button
          onClick={() => handleSubmit(query)}
          disabled={!fileId || isAnalyzing || !query.trim()}
          className="rounded-xl bg-[#2D3561] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#3a4578] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          →
        </button>
      </div>
    </section>
  );
}
