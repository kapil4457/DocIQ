"use client";

import React, { use, Suspense, useState, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  ArrowLeft,
  Loader2,
  FileText,
  MoreVertical,
  Upload,
  X,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Check,
  Download,
  Trash2,
  Pencil,
} from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { useAuth, canUploadDocuments } from "@/lib/auth";
import { uploadDocument, createUploadKeyTracker, mediaTypeFor } from "@/lib/upload";
import { apiFetch } from "@/lib/api";

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

interface GlobalDocumentsResponse {
  documents: DocRow[];
  total: number;
  page: number;
  pageSize: number;
}

const PAGE_SIZE = 8;

function statusBadge(status: DocVersion["status"]) {
  const map: Record<DocVersion["status"], string> = {
    available: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300",
    uploaded: "bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300",
    processing: "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300",
    ingesting: "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300",
    pending: "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300",
    aborted: "bg-zinc-100 text-zinc-700 dark:bg-zinc-900/50 dark:text-zinc-300",
  };
  const label: Record<DocVersion["status"], string> = {
    available: "Ready",
    uploaded: "Uploaded",
    processing: "Processing",
    ingesting: "Ingesting",
    pending: "Uploading",
    aborted: "Aborted",
  };
  return (
    <Badge className={map[status]}>
      {label[status]}
    </Badge>
  );
}

function statusDot(status: DocVersion["status"]) {
  const map: Record<DocVersion["status"], string> = {
    available: "bg-emerald-500",
    uploaded: "bg-sky-500",
    processing: "bg-violet-500",
    ingesting: "bg-violet-500",
    pending: "bg-amber-400",
    aborted: "bg-zinc-300 dark:bg-zinc-600",
  };
  return <span className={`absolute -left-[21px] size-2.5 rounded-full border-2 border-zinc-50 dark:border-zinc-900 ${map[status]}`} />;
}

function DeleteDialog({
  open,
  documentId,
  name,
  onClose,
  onDeleted,
}: {
  open: boolean;
  documentId: string;
  name: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remove = async () => {
    setDeleting(true);
    setError(null);
    try {
      await apiFetch(`/document/${documentId}`, { method: "DELETE" });
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Delete document</DialogTitle>
        <DialogDescription>Delete "{name}" permanently? All versions will be removed from storage.</DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
      <div className="space-y-4">
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="destructive" onClick={remove} disabled={deleting}>
            {deleting && <Loader2 className="size-4 animate-spin" />}
            {deleting ? "Deleting…" : "Delete document"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function DeleteVersionDialog({
  open,
  documentId,
  versionId,
  docName,
  onClose,
  onDeleted,
}: {
  open: boolean;
  documentId: string;
  versionId: string;
  docName: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remove = async () => {
    setDeleting(true);
    setError(null);
    try {
      await apiFetch(`/document/${documentId}/versions/${versionId}`, { method: "DELETE" });
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete version");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Delete version</DialogTitle>
        <DialogDescription>Delete this version of "{docName}"? This cannot be undone.</DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
      <div className="space-y-4">
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant="destructive" onClick={remove} disabled={deleting}>
            {deleting && <Loader2 className="size-4 animate-spin" />}
            {deleting ? "Deleting…" : "Delete version"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function DownloadButton({ documentId, versionId, fileName, disabled }: {
  documentId: string;
  versionId: string;
  fileName: string;
  disabled?: boolean;
}) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await apiFetch<{ url: string; filename: string }>(
        `/document/${documentId}/versions/${versionId}/download`
      );
      const a = document.createElement("a");
      a.href = res.url;
      a.download = res.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      console.error(err);
      alert("Download failed");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-7 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
      aria-label="Download this version"
      disabled={disabled || downloading}
      onClick={handleDownload}
    >
      {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <Download className="size-3.5" />}
    </Button>
  );
}

function GlobalUploadDialog({
  open,
  onClose,
  onUploaded,
}: {
  open: boolean;
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

  useEffect(() => {
    if (!open) return;
    setFile(null);
    setCustomName("");
    setError(null);
    setVersionOf("new");
    keyTracker.current.reset();
    apiFetch<{ documents: { documentId: string; name: string }[] }>(
      `/document/global?page=1&pageSize=100`
    )
      .then((res) => setExistingDocs(res.documents))
      .catch(() => setExistingDocs([]));
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Upload global document</DialogTitle>
        <DialogDescription>
          Available across every workspace in your organization. Workspace-specific files are uploaded from within a workspace.
        </DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
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
          <Label htmlFor="global-doc-version">Add as</Label>
          <select
            id="global-doc-version"
            value={versionOf}
            onChange={(e) => setVersionOf(e.target.value)}
            className="flex h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-950 shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950/15 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-50"
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
            <Label htmlFor="global-doc-name">Custom name</Label>
            <Input
              id="global-doc-name"
              placeholder={file ? file.name : "Name shown in the knowledge base"}
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
            />
          </div>
        )}
        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={!file || uploading}>
            {uploading && <Loader2 className="size-4 animate-spin" />}
            {uploading ? "Uploading…" : "Upload"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function GlobalDocumentsPanel({ isAdmin }: { isAdmin: boolean }) {
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [confirmDocId, setConfirmDocId] = useState<string | null>(null);
  const [confirmVersionId, setConfirmVersionId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<GlobalDocumentsResponse>(
        `/document/global?page=${p}&pageSize=${PAGE_SIZE}`
      );
      setDocs(res.documents);
      setTotal(res.total);
      setPage(res.page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(1);
  }, [load]);

  const onDeleteDoc = useCallback(() => {
    if (!confirmDocId) return;
    setDeleting(true);
    apiFetch(`/document/${confirmDocId}`, { method: "DELETE" })
      .then(() => {
        setConfirmDocId(null);
        load(page);
      })
      .catch((err) => alert(err instanceof Error ? err.message : "Delete failed"))
      .finally(() => setDeleting(false));
  }, [confirmDocId, page, load]);

  const onDeleteVersion = useCallback(() => {
    if (!confirmDocId || !confirmVersionId) return;
    setDeleting(true);
    apiFetch(`/document/${confirmDocId}/versions/${confirmVersionId}`, { method: "DELETE" })
      .then(() => {
        setConfirmDocId(null);
        setConfirmVersionId(null);
        load(page);
      })
      .catch((err) => alert(err instanceof Error ? err.message : "Delete failed"))
      .finally(() => setDeleting(false));
  }, [confirmDocId, confirmVersionId, page, load]);

  const handleUploaded = useCallback(() => {
    load(page);
  }, [load, page]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Global Documents</h1>
        {isAdmin && (
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="size-4 mr-2" />
            Upload
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-zinc-200/70 bg-white dark:border-zinc-700 dark:bg-zinc-900 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50/50 dark:bg-zinc-800/50">
            <tr className="border-b border-zinc-200 dark:border-zinc-700">
              <th className="px-4 py-3 text-left font-medium text-zinc-700 dark:text-zinc-300">Document</th>
              {isAdmin && (
                <th className="px-4 py-3 text-left font-medium text-zinc-700 dark:text-zinc-300">Versions</th>
              )}
              <th className="px-4 py-3 text-left font-medium text-zinc-700 dark:text-zinc-300">Created</th>
              <th className="px-4 py-3 text-right font-medium text-zinc-700 dark:text-zinc-300 w-32">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {loading && docs.length === 0 ? (
              <tr>
                <td colSpan={isAdmin ? 4 : 3} className="px-4 py-10 text-center">
                  <Loader2 className="size-6 animate-spin mx-auto text-zinc-400" />
                </td>
              </tr>
            ) : docs.length === 0 ? (
              <tr>
                <td colSpan={isAdmin ? 4 : 3} className="px-4 py-10 text-center text-zinc-500 dark:text-zinc-400">
                  No global documents available yet.
                </td>
              </tr>
            ) : (
              docs.map((doc) => (
                <React.Fragment key={doc.documentId}>
                  <tr className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-zinc-950/5 text-zinc-600 dark:bg-white/10 dark:text-zinc-300">
                          <FileText className="size-4" />
                        </span>
                        <div>
                          <p className="font-medium text-zinc-950 dark:text-zinc-50 truncate max-w-[300px]">{doc.name}</p>
                          <p className="text-xs text-zinc-500 dark:text-zinc-400">
                            {doc.versionCount} version{doc.versionCount !== 1 ? "s" : ""} · by {doc.uploadedByName ?? "Unknown"}
                          </p>
                        </div>
                      </div>
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                          onClick={() => setExpandedId(expandedId === doc.documentId ? null : doc.documentId)}
                        >
                          {doc.versionCount} version{doc.versionCount !== 1 ? "s" : ""}
                          <ChevronDown className={`size-3.5 ml-1 transition-transform ${expandedId === doc.documentId ? "rotate-180" : ""}`} />
                        </Button>
                      </td>
                    )}
                    <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400 whitespace-nowrap">
                      {new Date(doc.createdAt).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {isAdmin && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 text-zinc-400 hover:text-red-600 dark:hover:text-red-400"
                            onClick={() => setConfirmDocId(doc.documentId)}
                            aria-label={`Delete ${doc.name}`}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isAdmin && expandedId === doc.documentId && (
                    <tr className="border-b border-zinc-100 dark:border-zinc-800/50 animate-in rise-in-sm duration-300 ease-out-soft">
                      <td colSpan={4} className="px-3 pb-4 pt-1">
                        <div className="ml-6 max-h-56 overflow-y-auto rounded-xl border border-zinc-200/70 bg-zinc-50/60 p-3 dark:border-zinc-800 dark:bg-zinc-800/30">
                          <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                            Version trail · newest first
                          </p>
                          <ol className="relative space-y-2.5 border-l border-zinc-200 pl-4 dark:border-zinc-700">
                            {doc.versions.map((v) => (
                              <li key={v.versionId} className="relative flex items-center gap-2.5">
                                {statusDot(v.status)}
                                <div className="min-w-0 flex-1">
                                  <p className="flex items-center gap-2 text-xs">
                                    <span className="font-mono font-medium text-zinc-700 dark:text-zinc-300">
                                      {v.versionId.slice(0, 8)}
                                    </span>
                                    {v.status === "available" && v.isActive && (
                                      <Badge className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
                                        Used for response generation
                                      </Badge>
                                    )}
                                    {statusBadge(v.status)}
                                  </p>
                                  <p className="mt-0.5 text-[11px] text-zinc-500 dark:text-zinc-400">
                                    {v.uploadedByName ?? "Unknown"} · {new Date(v.createdAt).toLocaleString()}
                                    {v.fileSize !== null && ` · ${(v.fileSize / 1024).toFixed(0)} KB`}
                                  </p>
                                </div>
                                {v.status === "available" && (
                                  <DownloadButton
                                    documentId={doc.documentId}
                                    versionId={v.versionId}
                                    fileName={doc.name}
                                    disabled={deleting}
                                  />
                                )}
                                {confirmVersionId === v.versionId ? (
                                  <span className="inline-flex items-center gap-1">
                                    <Button
                                      variant="destructive"
                                      size="sm"
                                      onClick={onDeleteVersion}
                                      disabled={deleting}
                                    >
                                      {deleting ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                                      Sure?
                                    </Button>
                                    <Button variant="ghost" size="sm" onClick={() => setConfirmVersionId(null)}>
                                      Cancel
                                    </Button>
                                  </span>
                                ) : (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="size-7 text-zinc-400 hover:text-red-600 dark:hover:text-red-400"
                                    onClick={() => setConfirmVersionId(v.versionId)}
                                    disabled={deleting}
                                    aria-label="Delete this version"
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
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-zinc-200 px-4 py-3 dark:border-zinc-700">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Page {page} of {Math.ceil(total / PAGE_SIZE)} · {total} document{total !== 1 ? "s" : ""}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => load(page - 1)}
                disabled={page === 1 || loading}
              >
                <ChevronLeft className="size-4" />
                Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => load(page + 1)}
                disabled={page * PAGE_SIZE >= total || loading}
              >
                Next
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {confirmDocId && (
        <DeleteDialog
          open
          documentId={confirmDocId}
          name={docs.find((d) => d.documentId === confirmDocId)?.name ?? ""}
          onClose={() => setConfirmDocId(null)}
          onDeleted={() => load(page)}
        />
      )}
      {confirmVersionId && (
        <DeleteVersionDialog
          open
          documentId={confirmDocId!}
          versionId={confirmVersionId}
          docName={docs.find((d) => d.documentId === confirmDocId)?.name ?? ""}
          onClose={() => setConfirmVersionId(null)}
          onDeleted={() => load(page)}
        />
      )}
      {isAdmin && (
        <GlobalUploadDialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onUploaded={handleUploaded}
        />
      )}
    </div>
  );
}

export default function GlobalDocumentsPage() {
  const user = useAuth();
  const router = useRouter();

  const allowedRoles = ["org_admin", "org_super_admin", "participant"] as const;
  type AllowedRole = typeof allowedRoles[number];

  if (!user || !allowedRoles.includes(user.role as AllowedRole)) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-zinc-950 dark:text-zinc-50">Access denied</h1>
          <p className="mt-2 text-zinc-500 dark:text-zinc-400">You do not have permission to view global documents.</p>
          <Button variant="outline" onClick={() => router.push("/")} className="mt-4">
            <ArrowLeft className="size-4 mr-2" />
            Go home
          </Button>
        </div>
      </div>
    );
  }

  const isAdmin = user.role === "org_admin";

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 animate-in fade-in duration-300">
      <GlobalDocumentsPanel isAdmin={isAdmin} />
    </div>
  );
}