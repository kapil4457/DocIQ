"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { MessageSquare, FolderOpen, LogIn, Upload, LogOut, ChevronDown, FileText, Loader2, Building2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog";
import { useAuth, setUser, canUploadDocuments, type AuthUser } from "@/lib/auth";
import { uploadDocument, createUploadKeyTracker, mediaTypeFor } from "@/lib/upload";

export function Navbar() {
  const user = useAuth();
  const [workspacesOpen, setWorkspacesOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-200/60 bg-white/70 backdrop-blur-xl dark:border-zinc-800/60 dark:bg-zinc-950/70">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
          <span className="flex size-7 items-center justify-center rounded-lg bg-zinc-950 text-zinc-50 dark:bg-zinc-50 dark:text-zinc-950">
            <MessageSquare className="size-4" />
          </span>
          DocIQ
        </Link>

        <nav className="flex items-center gap-1.5">
          {user && user.role !== "super_admin" && (
            <WorkspacesButton userId={user.userId} open={workspacesOpen} onOpenChange={setWorkspacesOpen} />
          )}
          {canUploadDocuments(user) && <UploadButton open={uploadOpen} onOpenChange={setUploadOpen} />}
          {user?.role === "super_admin" && (
            <Link href="/manage-organizations">
              <Button variant="ghost" size="sm">
                <Building2 className="size-4" />
                Manage Organizations
              </Button>
            </Link>
          )}
          {user?.role === "org_super_admin" && (
            <Link href="/my-organization">
              <Button variant="ghost" size="sm">
                <Users className="size-4" />
                My Organization
              </Button>
            </Link>
          )}
          {user ? <AccountButton user={user} open={accountOpen} onOpenChange={setAccountOpen} /> : <AuthButtons />}
        </nav>
      </div>
    </header>
  );
}

function AuthButtons() {
  return (
    <div className="flex items-center gap-2">
      <Link href="/login">
        <Button size="sm">
          <LogIn className="size-4" />
          Log in
        </Button>
      </Link>
    </div>
  );
}

function AccountButton({
  user,
  open,
  onOpenChange,
}: {
  user: AuthUser;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const initials = user.name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="relative">
      <Button variant="ghost" size="sm" onClick={() => onOpenChange(!open)} aria-expanded={open}>
        <span className="flex size-6 items-center justify-center rounded-full bg-zinc-950 text-[10px] font-semibold text-zinc-50 dark:bg-zinc-100 dark:text-zinc-950">
          {initials}
        </span>
        <ChevronDown className="size-3.5 text-zinc-400" />
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => onOpenChange(false)} />
          <div className="absolute right-0 z-50 mt-2 w-60 rounded-xl border border-zinc-200/80 bg-white p-1.5 shadow-lg dark:border-zinc-800 dark:bg-zinc-900 origin-top-right animate-in drop-in duration-200 ease-out-soft">
            <div className="border-b border-zinc-100 px-3 py-2.5 dark:border-zinc-800">
              <p className="truncate text-sm font-medium text-zinc-950 dark:text-zinc-50">{user.name}</p>
              <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">{user.email}</p>
            </div>
            <div className="px-3 py-1.5">
              <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                {user.role.replace("_", " ")}
              </span>
            </div>
            <button
              onClick={() => {
                setUser(null);
                onOpenChange(false);
                router.push("/login");
              }}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40 transition-colors"
            >
              <LogOut className="size-4" />
              Log out
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function WorkspacesButton({
  userId,
  open,
  onOpenChange,
}: {
  userId: string | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<
    { id: string; name: string; messageCount: number; lastActive: string }[]
  >([]);
  const [loading, setLoading] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = () => {
    if (!userId) return;
    setLoading(true);
    // TODO: GET /workspace/list scoped to user once backend workspace endpoints return
    setTimeout(() => {
      setWorkspaces([]);
      setLoading(false);
    }, 300);
  };

  return (
    <div
      className="relative"
      onMouseEnter={() => {
        if (closeTimer.current) clearTimeout(closeTimer.current);
        load();
        onOpenChange(true);
      }}
      onMouseLeave={() => {
        closeTimer.current = setTimeout(() => onOpenChange(false), 200);
      }}
    >
      <Button variant="ghost" size="sm" onClick={() => onOpenChange(!open)}>
        <FolderOpen className="size-4" />
        Workspaces
      </Button>
      {open && (
        <div className="absolute left-1/2 z-50 mt-2 w-[380px] -translate-x-1/2">
          <div className="rounded-2xl border border-zinc-200/70 bg-white/95 shadow-2xl shadow-zinc-950/15 backdrop-blur-2xl dark:border-zinc-700/60 dark:bg-zinc-900/95 origin-top animate-in drop-in duration-300 ease-out-soft">
            <div className="flex items-center justify-between border-b border-zinc-200/50 px-4 py-3 dark:border-white/5">
              <p className="text-sm font-semibold text-zinc-950 dark:text-zinc-50">Your workspaces</p>
              <span className="text-xs text-zinc-400">{workspaces.length || ""}</span>
            </div>
            <div className="max-h-80 overflow-y-auto p-2">
              {!userId ? (
                <p className="px-3 py-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
                  Log in to see your workspaces
                </p>
              ) : loading ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="size-5 animate-spin text-zinc-400" />
                </div>
              ) : workspaces.length === 0 ? (
                <p className="px-3 py-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
                  No workspaces yet. Create one from the home page.
                </p>
              ) : (
                <ul className="space-y-1">
                  {workspaces.map((ws) => (
                    <li key={ws.id}>
                      <button
                        onClick={() => {
                          onOpenChange(false);
                          router.push(`/workspace/${ws.id}`);
                        }}
                        className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/80 dark:hover:bg-white/10"
                      >
                        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-zinc-950/5 text-zinc-600 dark:bg-white/10 dark:text-zinc-300">
                          <FileText className="size-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-zinc-950 dark:text-zinc-50">
                            {ws.name}
                          </span>
                          <span className="block text-xs text-zinc-500 dark:text-zinc-400">
                            {ws.messageCount} messages · {ws.lastActive}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function UploadButton({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [customName, setCustomName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const keyTracker = useRef(createUploadKeyTracker());

  useEffect(() => {
    if (open) setError(null);
  }, [open]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(
        file,
        {
          scope: "global",
          documentName: customName || file.name,
          mediaType: mediaTypeFor(file.name),
          fileSize: file.size,
        },
        keyTracker.current.keyFor(file),
      );
      onOpenChange(false);
      setFile(null);
      setCustomName("");
      keyTracker.current.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => onOpenChange(true)}>
        <Upload className="size-4" />
        Upload
      </Button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogHeader>
          <DialogTitle>Upload global document</DialogTitle>
          <DialogDescription>
            Available across every workspace in your organization. Workspace-specific files are uploaded from within a workspace.
          </DialogDescription>
        </DialogHeader>
        <DialogClose onClose={() => onOpenChange(false)} />
        <div className="space-y-4">
          <label
            className={`
              flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors
              ${
                file
                  ? "border-zinc-950/20 bg-zinc-50 dark:border-zinc-100/20 dark:bg-zinc-800/40"
                  : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:border-zinc-600 dark:hover:bg-zinc-800/40"
              }
            `}
          >
            <input
              type="file"
              className="sr-only"
              accept=".pdf,.docx,.txt,.md,.png,.html,.csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <FileText className="size-6 text-zinc-400" />
            {file ? (
              <span className="text-sm font-medium text-zinc-950 dark:text-zinc-50">{file.name}</span>
            ) : (
              <>
                <span className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                  Select a file
                </span>
                <span className="text-xs text-zinc-400">PDF, DOCX, TXT, MD, PNG, HTML or CSV</span>
              </>
            )}
          </label>
          <div className="space-y-1.5">
            <Label htmlFor="doc-name">Custom name</Label>
            <Input
              id="doc-name"
              placeholder={file ? file.name : "Name shown in the knowledge base"}
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
            />
          </div>
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpload} disabled={!file || uploading}>
              {uploading && <Loader2 className="size-4 animate-spin" />}
              {uploading ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  );
}
