"use client";

import { use, Suspense, useState, useRef, useEffect } from "react";
import { SendHorizontal, ArrowLeft, Loader2, FileText, MoreVertical } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
}

export default function WorkspacePage({ params }: PageProps<"/workspace/[id]">) {
  return (
    <Suspense fallback={
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-zinc-400" />
      </div>
    }>
      <WorkspaceInner params={params} />
    </Suspense>
  );
}

function WorkspaceInner({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [workspaceName, setWorkspaceName] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (id === "new") {
      const name = new URLSearchParams(window.location.search).get("name");
      setWorkspaceName(name ?? "New workspace");
      return;
    }
    // TODO: fetch workspace metadata + message history from backend
    setWorkspaceName("Workspace");
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const content = input.trim();
    if (!content || sending) return;
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setSending(true);

    const pendingId = crypto.randomUUID();
    setMessages((m) => [...m, { id: pendingId, role: "assistant", content: "", pending: true }]);

    try {
      // TODO: stream assistant responses from the chat endpoint
      await new Promise((r) => setTimeout(r, 1200));
      setMessages((m) =>
        m.map((msg) =>
          msg.id === pendingId
            ? {
                ...msg,
                pending: false,
                content:
                  "This is a placeholder response. The chat backend isn't connected yet. Once it is, answers will cite your uploaded documents here.",
              }
            : msg
        )
      );
    } catch {
      setMessages((m) =>
        m.map((msg) =>
          msg.id === pendingId
            ? { ...msg, pending: false, content: "Something went wrong. Try again." }
            : msg
        )
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pb-0 self-stretch">
      <div className="flex items-center gap-3 border-b border-zinc-200/70 py-3 dark:border-zinc-800/70">
        <Button variant="ghost" size="icon" onClick={() => router.push("/workspaces")} aria-label="Back to workspaces">
          <ArrowLeft className="size-4" />
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold">{workspaceName ?? "Workspace"}</h1>
          <p className="text-xs text-zinc-400">{id === "new" ? "Not saved yet" : id}</p>
        </div>
        <Badge>
          <FileText className="size-3" />
          0 docs
        </Badge>
        <Button variant="ghost" size="icon" aria-label="Workspace options">
          <MoreVertical className="size-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto py-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <span className="flex size-12 items-center justify-center rounded-2xl bg-zinc-950/5 dark:bg-white/10">
              <FileText className="size-6 text-zinc-500 dark:text-zinc-400" />
            </span>
            <h2 className="mt-4 text-base font-semibold">Start the conversation</h2>
            <p className="mt-1.5 max-w-sm text-sm text-zinc-500 dark:text-zinc-400">
              Ask a question about your documents, or upload some first for grounded answers.
            </p>
          </div>
        ) : (
          <ul className="space-y-6">
            {messages.map((msg) => (
              <li key={msg.id} className={`flex animate-in rise-in-sm duration-300 ease-out-soft ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={
                    msg.role === "user"
                      ? "max-w-[80%] rounded-2xl rounded-br-md bg-zinc-950 px-4 py-2.5 text-sm leading-6 text-zinc-50 dark:bg-zinc-100 dark:text-zinc-950"
                      : "max-w-[80%] rounded-2xl rounded-bl-md border border-zinc-200/70 bg-white px-4 py-2.5 text-sm leading-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900"
                  }
                >
                  {msg.pending ? (
                    <span className="flex items-center gap-1.5 py-0.5">
                      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:0ms]" />
                      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:150ms]" />
                      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:300ms]" />
                    </span>
                  ) : (
                    msg.content
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="sticky bottom-0 bg-gradient-to-t from-zinc-50 via-zinc-50 to-transparent pb-4 pt-2 dark:from-zinc-950 dark:via-zinc-950">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex items-end gap-2 rounded-2xl border border-zinc-200 bg-white p-2 shadow-lg shadow-zinc-950/5 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ask about your documents…"
            rows={1}
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-zinc-400"
          />
          <Button type="submit" size="icon" disabled={!input.trim() || sending} aria-label="Send message">
            {sending ? <Loader2 className="size-4 animate-spin" /> : <SendHorizontal className="size-4" />}
          </Button>
        </form>
      </div>
    </main>
  );
}
