"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2, MessageSquare, FileText, Sparkles, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();
  const user = useAuth();
  const [workspaceName, setWorkspaceName] = useState("");
  const [creating, setCreating] = useState(false);

  const createWorkspace = async () => {
    if (!workspaceName.trim() || !user) return;
    setCreating(true);
    try {
      // TODO: POST /workspace/create once wired; navigate to the new workspace
      await new Promise((r) => setTimeout(r, 600));
      router.push(`/workspace/new?name=${encodeURIComponent(workspaceName.trim())}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="flex-1">
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 50% -10%, rgba(99,112,255,0.12), transparent 70%), radial-gradient(ellipse 40% 40% at 80% 20%, rgba(16,185,129,0.07), transparent 70%)",
          }}
        />
        <div className="mx-auto max-w-3xl px-4 pb-20 pt-24 text-center sm:pt-32">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-200/80 bg-white/60 px-3 py-1 text-xs font-medium text-zinc-600 backdrop-blur animate-in rise-in-sm duration-500 ease-out-soft dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
            <Sparkles className="size-3.5" />
            Chat with your organization&apos;s knowledge
          </span>
          <h1 className="mt-6 text-balance text-4xl font-semibold tracking-tight animate-in rise-in duration-500 ease-out-soft delay-75 sm:text-5xl">
            DocIQ
            <br />
            <span className="text-zinc-400 dark:text-zinc-500">Ask anything. Get answers from your documents.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-lg text-pretty text-base leading-7 text-zinc-500 animate-in rise-in duration-500 ease-out-soft delay-150 dark:text-zinc-400">
            Every workspace is an isolated conversation. Start one, upload your documents, and keep
            each thread separate and focused.
          </p>

          <Card className="mx-auto mt-10 max-w-md text-left shadow-lg shadow-zinc-950/5 animate-in rise-in duration-500 ease-out-soft delay-225">
            {user?.role === "super_admin" ? (
              <>
                <CardHeader>
                  <CardTitle className="text-base">Super admin console</CardTitle>
                  <CardDescription>
                    Platform administration only. Workspaces live inside organizations.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <a href="/manage-organizations">
                    <Button className="w-full">
                      <Building2 className="size-4" />
                      Manage Organizations
                    </Button>
                  </a>
                </CardContent>
              </>
            ) : (
              <>
                <CardHeader>
                  <CardTitle className="text-base">New workspace</CardTitle>
                  <CardDescription>
                    {user ? "Name the conversation, then start chatting." : "Log in to create a workspace."}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2">
                    <Input
                      placeholder="e.g. Q3 contract review"
                      value={workspaceName}
                      onChange={(e) => setWorkspaceName(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && createWorkspace()}
                      disabled={!user || creating}
                    />
                    <Button onClick={createWorkspace} disabled={!user || !workspaceName.trim() || creating}>
                      {creating ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                      Create
                    </Button>
                  </div>
                  {!user && (
                    <p className="mt-3 text-center text-sm text-zinc-500 dark:text-zinc-400">
                      Accounts are created by your organization&apos;s administrator.{" "}
                      <a href="/login" className="font-medium text-zinc-950 underline underline-offset-4 dark:text-zinc-50">
                        Log in
                      </a>
                      .
                    </p>
                  )}
                </CardContent>
              </>
            )}
          </Card>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 pb-24">
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            {
              icon: MessageSquare,
              title: "Isolated sessions",
              body: "Each workspace keeps its own chat history and context. Nothing bleeds across threads.",
            },
            {
              icon: FileText,
              title: "Your documents",
              body: "Uploads are scoped to your organization or a single workspace, so answers cite the right sources.",
            },
            {
              icon: Sparkles,
              title: "Grounded answers",
              body: "Document-aware responses with citations back to the exact version of the file they came from.",
            },
          ].map(({ icon: Icon, title, body }, i) => (
            <div
              key={title}
              className={`rounded-2xl border border-zinc-200/70 bg-white/50 p-5 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:shadow-zinc-950/5 dark:border-zinc-800/70 dark:bg-zinc-900/40 dark:hover:shadow-black/30 animate-in rise-in duration-500 ease-out-soft ${
                ["", "delay-75", "delay-150"][i]
              }`}
            >
              <span className="flex size-9 items-center justify-center rounded-xl bg-zinc-950/5 text-zinc-700 transition-colors duration-300 group-hover:bg-zinc-950 dark:bg-white/10 dark:text-zinc-300">
                <Icon className="size-4.5" />
              </span>
              <h3 className="mt-3.5 text-sm font-semibold">{title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-zinc-500 dark:text-zinc-400">{body}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
