"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, Plus, Users, Loader2, FolderOpen, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

interface WorkspaceRow {
  id: string;
  name: string;
  creatorId: string;
  memberCount: number;
}

interface PagedWorkspaces {
  workspaces: WorkspaceRow[];
  total: number;
  page: number;
  pageSize: number;
}

const PAGE_SIZE = 9;

export default function WorkspacesPage() {
  const router = useRouter();
  const user = useAuth();
  const [data, setData] = useState<PagedWorkspaces | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const load = useCallback(
    async (p: number) => {
      if (!user?.userId) {
        setLoading(false);
        return;
      }
      if (user.role === "super_admin") {
        router.replace("/");
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await apiFetch<PagedWorkspaces>(`/workspace/list?page=${p}&pageSize=${PAGE_SIZE}`);
        setData(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load workspaces");
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [user?.userId, user?.role, router]
  );

  useEffect(() => {
    load(page);
  }, [load, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Your workspaces</h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Pick up any conversation where you left off.
          </p>
        </div>
        {user?.role !== "super_admin" && (
          <Button onClick={() => router.push("/")} className="cursor-pointer">
            <Plus className="size-4" />
            New workspace
          </Button>
        )}
      </div>

      <div className="mt-8">
        {!user ? (
          <EmptyState
            icon={FolderOpen}
            title="Log in to view workspaces"
            body="Your conversation history lives here once you have an account."
            action={<Button onClick={() => router.push("/login")} className="cursor-pointer">Log in</Button>}
          />
        ) : loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="size-6 animate-spin text-zinc-400" />
          </div>
        ) : error ? (
          <EmptyState
            icon={FolderOpen}
            title="Could not load workspaces"
            body={error}
            action={<Button variant="outline" onClick={() => load(page)} className="cursor-pointer">Try again</Button>}
          />
        ) : !data || data.workspaces.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="No workspaces yet"
            body="Create your first workspace from the home page to start a conversation."
            action={
              <Button onClick={() => router.push("/")} className="cursor-pointer">
                <Plus className="size-4" />
                Create workspace
              </Button>
            }
          />
        ) : (
          <>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.workspaces.map((ws, i) => (
                <li
                  key={ws.id}
                  className={`animate-in rise-in duration-500 ease-out-soft ${["", "delay-75", "delay-150"][i % 3]}`}
                >
                  <button
                    onClick={() => router.push(`/workspace/${ws.id}`)}
                    className="group flex h-full w-full cursor-pointer flex-col gap-3 rounded-2xl border border-zinc-200/70 bg-white/60 p-4 text-left backdrop-blur-sm transition-all duration-300 hover:border-zinc-300 hover:bg-white hover:shadow-md hover:shadow-zinc-950/5 hover:-translate-y-0.5 dark:border-zinc-800/70 dark:bg-zinc-900/50 dark:hover:border-zinc-700 dark:hover:bg-zinc-900 dark:hover:shadow-black/30"
                  >
                    <span className="flex size-10 items-center justify-center rounded-xl bg-zinc-950/5 text-zinc-600 transition-colors group-hover:bg-zinc-950 group-hover:text-zinc-50 dark:bg-white/10 dark:text-zinc-300 dark:group-hover:bg-zinc-100 dark:group-hover:text-zinc-950">
                      <MessageSquare className="size-5" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{ws.name}</span>
                      <span className="mt-1 flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
                        <Users className="size-3" />
                        {ws.memberCount} {ws.memberCount === 1 ? "member" : "members"}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>

            <Pagination
              page={data.page}
              totalPages={totalPages}
              total={data.total}
              onPageChange={setPage}
            />
          </>
        )}
      </div>
    </main>
  );
}

function Pagination({
  page,
  totalPages,
  total,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (p: number) => void;
}) {
  return (
    <div className="mt-8 flex items-center justify-between border-t border-zinc-200/70 pt-4 dark:border-zinc-800/70">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        {total} {total === 1 ? "workspace" : "workspaces"}
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)} className="cursor-pointer disabled:cursor-not-allowed">
          <ChevronLeft className="size-4" />
          Prev
        </Button>
        <span className="px-2 text-sm text-zinc-600 tabular-nums dark:text-zinc-300">
          {page} of {totalPages}
        </span>
        <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} className="cursor-pointer disabled:cursor-not-allowed">
          Next
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
  action: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-zinc-300 px-6 py-20 text-center dark:border-zinc-700">
      <span className="flex size-12 items-center justify-center rounded-2xl bg-zinc-950/5 text-zinc-500 dark:bg-white/10 dark:text-zinc-400">
        <Icon className="size-6" />
      </span>
      <h2 className="mt-4 text-base font-semibold">{title}</h2>
      <p className="mt-1.5 max-w-sm text-sm text-zinc-500 dark:text-zinc-400">{body}</p>
      <div className="mt-5">{action}</div>
    </div>
  );
}
