"use client";

import { use, Suspense, useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { uploadDocument, createUploadKeyTracker, mediaTypeFor } from "@/lib/upload";
import { useToastHelpers } from "@/components/ui/toast";
import {
  SendHorizontal,
  ArrowLeft,
  Loader2,
  FileText,
  MoreVertical,
  Upload,
  Users,
  Pencil,
  Trash2,
  X,
  UserPlus,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Check,
  Download,
} from "lucide-react";

const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500 MB
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
}

interface WorkspaceDetail {
  id: string;
  name: string;
  creatorId: string;
  memberCount: number;
}

interface MemberRow {
  id: string;
  name: string;
  email: string;
  role: string;
  isCreator: boolean;
}

export default function WorkspacePage({ params }: PageProps<"/workspace/[id]">) {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="size-6 animate-spin text-zinc-400" />
        </div>
      }
    >
      <WorkspaceInner params={params} />
    </Suspense>
  );
}

function WorkspaceInner({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const user = useAuth();
  const [workspace, setWorkspace] = useState<WorkspaceDetail | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [docsOpen, setDocsOpen] = useState(false);
  const [docCount, setDocCount] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const isCreator = workspace?.creatorId === user?.userId;
  const canManage = isCreator || user?.role === "org_super_admin";

  const loadWorkspace = useCallback(async () => {
    if (id === "new") {
      const name = new URLSearchParams(window.location.search).get("name");
      setWorkspace({ id: "new", name: name ?? "New workspace", creatorId: user?.userId ?? "", memberCount: 1 });
      return;
    }
    try {
      const detail = await apiFetch<WorkspaceDetail>(`/workspace/${id}`);
      setWorkspace(detail);
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : "Failed to load workspace");
    }
  }, [id, user?.userId]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const openMenu = () => {
    if (menuOpen) {
      setMenuOpen(false);
      return;
    }
    const btn = menuBtnRef.current;
    if (btn) {
      const rect = btn.getBoundingClientRect();
      setMenuPos({ top: rect.bottom + 4, left: rect.right - 224 });
    }
    setMenuOpen(true);
  };

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
          msg.id === pendingId ? { ...msg, pending: false, content: "Something went wrong. Try again." } : msg
        )
      );
    } finally {
      setSending(false);
    }
  };

  if (workspaceError) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-3 px-4 text-center">
        <FileText className="size-10 text-zinc-300 dark:text-zinc-600" />
        <p className="text-sm text-zinc-500 dark:text-zinc-400">{workspaceError}</p>
        <Button variant="outline" size="sm" onClick={() => router.push("/workspaces")}>
          Back to workspaces
        </Button>
      </main>
    );
  }

  if (!workspace) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-zinc-400" />
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pb-0 self-stretch">
      <div className="flex items-center gap-3 border-b border-zinc-200/70 py-3 dark:border-zinc-800/70">
        <Button variant="ghost" size="icon" onClick={() => router.push("/workspaces")} aria-label="Back to workspaces">
          <ArrowLeft className="size-4" />
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold">{workspace.name}</h1>
          <p className="text-xs text-zinc-400">
            {workspace.memberCount} {workspace.memberCount === 1 ? "member" : "members"}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setDocsOpen(true)}>
          <FileText className="size-4" />
          Documents{docCount !== null ? ` (${docCount})` : ""}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setUploadOpen(true)}>
          <Upload className="size-4" />
          Upload
        </Button>
        <div className="relative">
          <Button ref={menuBtnRef} variant="ghost" size="icon" onClick={openMenu} aria-label="Workspace options" aria-expanded={menuOpen}>
            <MoreVertical className="size-4" />
          </Button>
        </div>
        {menuOpen && menuPos && (
          <WorkspaceMenu
            pos={menuPos}
            canManage={canManage}
            onClose={() => setMenuOpen(false)}
            onShare={() => setShareOpen(true)}
            onRename={() => setRenameOpen(true)}
            onDelete={() => setDeleteOpen(true)}
          />
        )}
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

      <RenameDialog
        open={renameOpen}
        workspace={workspace}
        onClose={() => setRenameOpen(false)}
        onRenamed={(name) => setWorkspace({ ...workspace, name })}
      />
      <ShareDialog open={shareOpen} workspaceId={workspace.id} canManage={canManage} onClose={() => setShareOpen(false)} />
      <DeleteDialog open={deleteOpen} workspaceId={workspace.id} name={workspace.name} onClose={() => setDeleteOpen(false)} />
      <UploadDialog
        open={uploadOpen}
        workspaceId={workspace.id}
        workspaceName={workspace.name}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => loadWorkspace()}
      />
      <DocumentsPanel
        open={docsOpen}
        workspaceId={workspace.id}
        onClose={() => setDocsOpen(false)}
        onChanged={() => loadWorkspace()}
        onCountChange={setDocCount}
      />
    </main>
  );
}

function WorkspaceMenu({
  pos,
  canManage,
  onClose,
  onShare,
  onRename,
  onDelete,
}: {
  pos: { top: number; left: number };
  canManage: boolean;
  onClose: () => void;
  onShare: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  if (typeof document === "undefined") return null;
  return createPortal(
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        className="fixed z-50 w-48 rounded-xl border border-zinc-200/80 bg-white p-1.5 shadow-lg dark:border-zinc-800 dark:bg-zinc-900 origin-top-right animate-in drop-in duration-200 ease-out-soft"
        style={{ top: pos.top, left: pos.left }}
      >
        <button
          onClick={() => {
            onClose();
            onShare();
          }}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
        >
          <Users className="size-4 text-zinc-400" />
          Members
        </button>
        {canManage && (
          <>
            <button
              onClick={() => {
                onClose();
                onRename();
              }}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
            >
              <Pencil className="size-4 text-zinc-400" />
              Rename
            </button>
            <button
              onClick={() => {
                onClose();
                onDelete();
              }}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40 transition-colors cursor-pointer"
            >
              <Trash2 className="size-4" />
              Delete workspace
            </button>
          </>
        )}
      </div>
    </>,
    document.body
  );
}

function RenameDialog({
  open,
  workspace,
  onClose,
  onRenamed,
}: {
  open: boolean;
  workspace: WorkspaceDetail;
  onClose: () => void;
  onRenamed: (name: string) => void;
}) {
  const [name, setName] = useState(workspace.name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setName(workspace.name ?? "");
      setError(null);
    }
  }, [open, workspace.name]);

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/workspace/${workspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      onRenamed(name);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename workspace");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Rename workspace</DialogTitle>
        <DialogDescription>Pick a name that tells people what this thread is for.</DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="ws-rename">Workspace name</Label>
          <Input id="ws-rename" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={!name.trim() || saving}>
            {saving && <Loader2 className="size-4 animate-spin" />}
            Save
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function ShareDialog({
  open,
  workspaceId,
  canManage,
  onClose,
}: {
  open: boolean;
  workspaceId: string;
  canManage: boolean;
  onClose: () => void;
}) {
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    apiFetch<{ members: MemberRow[] }>(`/workspace/${workspaceId}/members`)
      .then((res) => setMembers(res.members))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load members"))
      .finally(() => setLoading(false));
  }, [open, workspaceId]);

  const addMember = async () => {
    setAdding(true);
    setError(null);
    try {
      await apiFetch(`/workspace/${workspaceId}/members`, {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setEmail("");
      const res = await apiFetch<{ members: MemberRow[] }>(`/workspace/${workspaceId}/members`);
      setMembers(res.members);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add member");
    } finally {
      setAdding(false);
    }
  };

  const removeMember = async (memberId: string) => {
    try {
      await apiFetch(`/workspace/${workspaceId}/members/${memberId}`, { method: "DELETE" });
      setMembers((m) => m.filter((x) => x.id !== memberId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove member");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Workspace members</DialogTitle>
        <DialogDescription>
          {canManage
            ? "Share this workspace with people in your organization."
            : "People who have access to this workspace."}
        </DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
      <div className="space-y-4">
        {canManage && (
          <div className="flex gap-2">
            <Input
              type="email"
              placeholder="teammate@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Button onClick={addMember} disabled={!email.trim() || adding}>
              {adding ? <Loader2 className="size-4 animate-spin" /> : <UserPlus className="size-4" />}
              Add
            </Button>
          </div>
        )}
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>}
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="size-5 animate-spin text-zinc-400" />
          </div>
        ) : (
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {members.map((m) => (
              <li key={m.id} className="flex items-center gap-3 rounded-xl px-3 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-zinc-950/5 text-[11px] font-semibold text-zinc-600 dark:bg-white/10 dark:text-zinc-300">
                  {m.name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{m.name}</span>
                  <span className="block truncate text-xs text-zinc-500 dark:text-zinc-400">{m.email}</span>
                </span>
                {m.isCreator ? (
                  <Badge>creator</Badge>
                ) : (
                  canManage && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 text-zinc-400 hover:text-red-600 dark:hover:text-red-400"
                      aria-label={`Remove ${m.name}`}
                      onClick={() => removeMember(m.id)}
                    >
                      <X className="size-4" />
                    </Button>
                  )
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Dialog>
  );
}

function DeleteDialog({
  open,
  workspaceId,
  name,
  onClose,
}: {
  open: boolean;
  workspaceId: string;
  name: string;
  onClose: () => void;
}) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remove = async () => {
    setDeleting(true);
    setError(null);
    try {
      await apiFetch(`/workspace/${workspaceId}`, { method: "DELETE" });
      router.push("/workspaces");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete workspace");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Delete workspace</DialogTitle>
        <DialogDescription>
          Delete "{name}" permanently? Messages in it will be lost. Members keep their accounts.
        </DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
      <div className="space-y-4">
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="destructive" onClick={remove} disabled={deleting}>
            {deleting && <Loader2 className="size-4 animate-spin" />}
            {deleting ? "Deleting…" : "Delete workspace"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function UploadDialog({
  open,
  workspaceId,
  workspaceName,
  onClose,
  onUploaded,
}: {
  open: boolean;
  workspaceId: string;
  workspaceName: string;
  onClose: () => void;
  onUploaded: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [customName, setCustomName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingDocs, setExistingDocs] = useState<{ documentId: string; name: string }[]>([]);
  const [versionOf, setVersionOf] = useState<string>("new");
  const keyTracker = useRef(createUploadKeyTracker());
  const { success, error: toastError } = useToastHelpers();

  useEffect(() => {
    if (!open) return;
    setFile(null);
    setCustomName("");
    setError(null);
    setVersionOf("new");
    keyTracker.current.reset();
    apiFetch<{ documents: { documentId: string; name: string }[] }>(
      `/document/list?workspaceId=${workspaceId}&pageSize=100`
    )
      .then((res) => setExistingDocs(res.documents))
      .catch(() => setExistingDocs([]));
  }, [open, workspaceId]);

  const startUpload = async () => {
    if (!file) return;
    if (file.size > MAX_FILE_SIZE) {
      setError(`File size exceeds maximum allowed limit of ${MAX_FILE_SIZE / (1024 * 1024)} MB`);
      toastError("Upload failed", `File size exceeds maximum allowed limit of ${MAX_FILE_SIZE / (1024 * 1024)} MB`);
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(
        file,
        {
          scope: "workspace",
          workspaceId,
          documentId: versionOf === "new" ? null : versionOf,
          documentName: customName || file.name,
          mediaType: mediaTypeFor(file.name),
          fileSize: file.size,
        },
        keyTracker.current.keyFor(file),
      );

      onUploaded();
      onClose();
      setFile(null);
      setCustomName("");
      keyTracker.current.reset();
      success("Upload complete", "Document uploaded successfully");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setError(msg);
      toastError("Upload failed", msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Upload to {workspaceName}</DialogTitle>
        <DialogDescription>This document will only be available inside this workspace.</DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
      <div className="space-y-4">
        <label
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ${
            file
              ? "border-zinc-950/20 bg-zinc-50 dark:border-zinc-100/20 dark:bg-zinc-800/40"
              : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:border-zinc-600 dark:hover:bg-zinc-800/40"
          }`}
        >
          <input
            type="file"
            className="sr-only"
            accept=".pdf,.docx,.txt,.md,.png,.html,.csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <FileText className="size-6 text-zinc-400" />
          {file ? (
            <span className="text-sm font-medium">{file.name}</span>
          ) : (
            <>
              <span className="text-sm font-medium">Select a file</span>
              <span className="text-xs text-zinc-400">PDF, DOCX, TXT, MD, PNG, HTML or CSV · Max 500 MB</span>
            </>
          )}
        </label>
        <div className="space-y-1.5">
          <Label htmlFor="ws-doc-version">Add as</Label>
          <select
            id="ws-doc-version"
            value={versionOf}
            onChange={(e) => setVersionOf(e.target.value)}
            className="flex h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-950 shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950/15 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-50 cursor-pointer"
          >
            <option value="new">New document</option>
            {existingDocs.map((d) => (
              <option key={d.documentId} value={d.documentId}>
                New version of: {d.name}
              </option>
            ))}
          </select>
        </div>
        {versionOf === "new" && (
          <div className="space-y-1.5">
            <Label htmlFor="ws-doc-name">Custom name</Label>
            <Input
              id="ws-doc-name"
              placeholder={file ? file.name : "Name shown in the workspace"}
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
            />
          </div>
        )}
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} className="cursor-pointer">Cancel</Button>
          <Button onClick={startUpload} disabled={!file || uploading} className="cursor-pointer disabled:cursor-not-allowed">
            {uploading && <Loader2 className="size-4 animate-spin" />}
            {uploading ? "Uploading…" : "Upload"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

interface DocVersion {
  versionId: string;
  status: "pending" | "uploaded" | "processing" | "ingesting" | "available" | "aborted";
  isActive: boolean;
  uploadedByName: string | null;
  fileSize: number | null;
  createdAt: string;
}

interface DocRow {
  documentId: string;
  name: string;
  uploadedByName: string | null;
  createdAt: string;
  versionCount: number;
  versions: DocVersion[];
}

function DocumentsPanel({
  open,
  workspaceId,
  onClose,
  onChanged,
  onCountChange,
}: {
  open: boolean;
  workspaceId: string;
  onClose: () => void;
  onChanged: () => void;
  onCountChange: (count: number) => void;
}) {
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [confirmDocId, setConfirmDocId] = useState<string | null>(null);
  const [confirmVersionId, setConfirmVersionId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [downloadingVersionId, setDownloadingVersionId] = useState<string | null>(null);
  const PAGE_SIZE = 8;

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<PagedDocs>(`/document/list?workspaceId=${workspaceId}&page=${p}&pageSize=${PAGE_SIZE}`);
      setDocs(res.documents);
      setTotal(res.total);
      onCountChange(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, onCountChange]);

  useEffect(() => {
    if (open) {
      setPage(1);
      setExpandedId(null);
      setConfirmDocId(null);
      setConfirmVersionId(null);
      load(1);
    }
  }, [open, load]);

  useEffect(() => {
    if (open) load(page);
  }, [page, open, load]);

  if (!open || typeof document === "undefined") return null;

  const deleteDocument = async (documentId: string) => {
    setDeleting(true);
    try {
      await apiFetch(`/document/${documentId}`, { method: "DELETE" });
      setConfirmDocId(null);
      const remainingOnPage = docs.length - 1;
      if (remainingOnPage === 0 && page > 1) setPage(page - 1);
      else await load(page);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document");
    } finally {
      setDeleting(false);
    }
  };

  const deleteVersion = async (documentId: string, versionId: string) => {
    setDeleting(true);
    try {
      await apiFetch(`/document/${documentId}/versions/${versionId}`, { method: "DELETE" });
      setConfirmVersionId(null);
      await load(page);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete version");
    } finally {
      setDeleting(false);
    }
  };

  const downloadVersion = async (documentId: string, versionId: string, fallbackName: string) => {
    setDownloadingVersionId(versionId);
    try {
      const res = await apiFetch<{ url: string; filename: string }>(
        `/document/${documentId}/versions/${versionId}/download`
      );
      const anchor = window.document.createElement("a");
      anchor.href = res.url;
      anchor.download = res.filename || fallbackName;
      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start download");
    } finally {
      setDownloadingVersionId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="absolute inset-0 bg-zinc-950/40 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose} />
      <div className="relative z-10 w-full max-w-3xl rounded-2xl border border-zinc-200/80 bg-white shadow-xl animate-in slide-up-fade duration-300 ease-out-soft dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-between border-b border-zinc-200/70 px-5 py-4 dark:border-zinc-800/70">
          <div>
            <h2 className="text-base font-semibold tracking-tight">Workspace documents</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {total} {total === 1 ? "document" : "documents"} · click a row to see its version trail
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X className="size-4" />
          </Button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="size-6 animate-spin text-zinc-400" />
            </div>
          ) : error ? (
            <p className="py-8 text-center text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : docs.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-14 text-center">
              <FileText className="size-8 text-zinc-300 dark:text-zinc-600" />
              <p className="text-sm font-medium">No documents yet</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Use the Upload button to add the first one.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200/70 text-left text-xs uppercase tracking-wider text-zinc-400 dark:border-zinc-800/70">
                  <th className="px-3 py-2.5 font-medium">Document</th>
                  <th className="px-3 py-2.5 font-medium">Versions</th>
                  <th className="px-3 py-2.5 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => (
                  <DocumentRow
                    key={doc.documentId}
                    doc={doc}
                    expanded={expandedId === doc.documentId}
                    onToggle={() => setExpandedId(expandedId === doc.documentId ? null : doc.documentId)}
                    confirmDocDelete={confirmDocId === doc.documentId}
                    onConfirmDocDelete={() => setConfirmDocId(doc.documentId)}
                    onCancelDocDelete={() => setConfirmDocId(null)}
                    onDeleteDoc={() => deleteDocument(doc.documentId)}
                    confirmVersionId={confirmVersionId}
                    onConfirmVersionDelete={(vid) => setConfirmVersionId(vid)}
                    onCancelVersionDelete={() => setConfirmVersionId(null)}
                    onDeleteVersion={(vid) => deleteVersion(doc.documentId, vid)}
                    deleting={deleting}
                    downloadingVersionId={downloadingVersionId}
                    onDownloadVersion={(vid, name) => downloadVersion(doc.documentId, vid, name)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-zinc-200/70 px-5 py-3 dark:border-zinc-800/70">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">{total} total</p>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                <ChevronLeft className="size-4" />
                Prev
              </Button>
              <span className="px-2 text-sm tabular-nums text-zinc-600 dark:text-zinc-300">
                {page} of {totalPages}
              </span>
              <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                Next
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

interface PagedDocs {
  documents: DocRow[];
  total: number;
  page: number;
  pageSize: number;
}

function DocumentRow({
  doc,
  expanded,
  onToggle,
  confirmDocDelete,
  onConfirmDocDelete,
  onCancelDocDelete,
  onDeleteDoc,
  confirmVersionId,
  onConfirmVersionDelete,
  onCancelVersionDelete,
  onDeleteVersion,
  deleting,
  downloadingVersionId,
  onDownloadVersion,
}: {
  doc: DocRow;
  expanded: boolean;
  onToggle: () => void;
  confirmDocDelete: boolean;
  onConfirmDocDelete: () => void;
  onCancelDocDelete: () => void;
  onDeleteDoc: () => void;
  confirmVersionId: string | null;
  onConfirmVersionDelete: (vid: string) => void;
  onCancelVersionDelete: () => void;
  onDeleteVersion: (vid: string) => void;
  deleting: boolean;
  downloadingVersionId: string | null;
  onDownloadVersion: (vid: string, filename: string) => void;
}) {
  return (
    <>
      <tr
        className={`border-b border-zinc-100 cursor-pointer transition-colors hover:bg-zinc-50/70 dark:border-zinc-800/50 dark:hover:bg-zinc-800/30 ${expanded ? "bg-zinc-50/70 dark:bg-zinc-800/30" : ""}`}
        onClick={onToggle}
      >
        <td className="px-3 py-3">
          <div className="flex items-center gap-2.5">
            <ChevronDown className={`size-4 text-zinc-400 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`} />
            <FileText className="size-4 shrink-0 text-zinc-400" />
            <div className="min-w-0">
              <p className="truncate font-medium">{doc.name}</p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                by {doc.uploadedByName ?? "Unknown"} · {new Date(doc.createdAt).toLocaleDateString()}
              </p>
            </div>
          </div>
        </td>
        <td className="px-3 py-3">
          <Badge>
            {doc.versionCount} {doc.versionCount === 1 ? "version" : "versions"}
          </Badge>
        </td>
        <td className="px-3 py-3 text-right" onClick={(e) => e.stopPropagation()}>
          {confirmDocDelete ? (
            <span className="inline-flex items-center gap-1.5">
              <Button variant="destructive" size="sm" onClick={onDeleteDoc} disabled={deleting}>
                {deleting ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                Delete trail
              </Button>
              <Button variant="ghost" size="sm" onClick={onCancelDocDelete}>Cancel</Button>
            </span>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              className="size-8 text-zinc-400 hover:text-red-600 dark:hover:text-red-400 cursor-pointer"
              aria-label={`Delete ${doc.name}`}
              onClick={onConfirmDocDelete}
            >
              <Trash2 className="size-4" />
            </Button>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-zinc-100 dark:border-zinc-800/50">
          <td colSpan={3} className="px-3 pb-4 pt-1">
            <div className="ml-6 max-h-56 overflow-y-auto rounded-xl border border-zinc-200/70 bg-zinc-50/60 p-3 dark:border-zinc-800 dark:bg-zinc-800/30">
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                Version trail · newest first
              </p>
              <ol className="relative space-y-2.5 border-l border-zinc-200 pl-4 dark:border-zinc-700">
                {doc.versions.map((v) => (
                  <li key={v.versionId} className="relative flex items-center gap-2.5 animate-in rise-in-sm duration-300 ease-out-soft">
                    <span
                      className={`absolute -left-[21px] size-2.5 rounded-full border-2 border-zinc-50 dark:border-zinc-900 ${
                        v.status === "available"
                          ? "bg-emerald-500"
                          : v.status === "uploaded"
                            ? "bg-sky-500"
                            : v.status === "processing" || v.status === "ingesting"
                              ? "bg-violet-500"
                              : v.status === "pending"
                                ? "bg-amber-400"
                                : "bg-zinc-300 dark:bg-zinc-600"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 text-xs">
                        <span className="font-mono font-medium text-zinc-700 dark:text-zinc-300">
                          {v.versionId.slice(0, 8)}
                        </span>
                        {v.status === "available" && v.isActive && (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
                            Used for response generation
                          </span>
                        )}
                        <Badge className={(
                          v.status === "available" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300" :
                          v.status === "uploaded" ? "bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300" :
                          v.status === "processing" || v.status === "ingesting" ? "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300" :
                          v.status === "pending" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300" :
                          "bg-zinc-100 text-zinc-700 dark:bg-zinc-900/50 dark:text-zinc-300"
                        )}>
                          {v.status === "available" ? "Ready" :
                           v.status === "uploaded" ? "Uploaded" :
                           v.status === "processing" ? "Processing" :
                           v.status === "ingesting" ? "Ingesting" :
                           v.status === "pending" ? "Uploading" : "Aborted"}
                        </Badge>
                      </p>
                      <p className="mt-0.5 text-[11px] text-zinc-500 dark:text-zinc-400">
                        {v.uploadedByName ?? "Unknown"} · {new Date(v.createdAt).toLocaleString()}
                        {v.fileSize !== null && ` · ${(v.fileSize / 1024).toFixed(0)} KB`}
                      </p>
                    </div>
                    {(v.status === "available" || v.status === "uploaded") && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 cursor-pointer"
                        aria-label="Download this version"
                        disabled={downloadingVersionId === v.versionId}
                        onClick={() => onDownloadVersion(v.versionId, doc.name)}
                      >
                        {downloadingVersionId === v.versionId
                          ? <Loader2 className="size-3.5 animate-spin" />
                          : <Download className="size-3.5" />}
                      </Button>
                    )}
                    {confirmVersionId === v.versionId ? (
                      <span className="inline-flex items-center gap-1">
                        <Button variant="destructive" size="sm" onClick={() => onDeleteVersion(v.versionId)} disabled={deleting} className="cursor-pointer disabled:cursor-not-allowed">
                          {deleting ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                          Sure?
                        </Button>
                        <Button variant="ghost" size="sm" onClick={onCancelVersionDelete} className="cursor-pointer">Cancel</Button>
                      </span>
                    ) : (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7 text-zinc-300 hover:text-red-600 dark:text-zinc-600 dark:hover:text-red-400 cursor-pointer"
                        aria-label="Delete this version"
                        onClick={() => onConfirmVersionDelete(v.versionId)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
