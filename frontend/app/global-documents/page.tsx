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
  ShieldAlert,
  Info,
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
import { useToastHelpers } from "@/components/ui/toast";

const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500 MB

interface DocVersion {
  versionId: string;
  status: "pending" | "uploaded" | "security_pending" | "security_running" | "security_failed" | "processing" | "ingesting" | "processing_failed" | "available" | "aborted" | "quarantined";
  isActive: boolean;
  uploadedByName: string | null;
  fileSize: number | null;
  createdAt: string;
  quarantineReason?: string | null;
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

/** Human-readable file size: B / KB / MB / GB with sensible precision. */
function formatFileSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb >= 100 ? kb.toFixed(0) : kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb >= 100 ? mb.toFixed(0) : mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

function statusBadge(status: DocVersion["status"]) {
  const map: Record<DocVersion["status"], string> = {
    available: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300",
    uploaded: "bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300",
    security_pending: "bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300",
    security_running: "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300",
    security_failed: "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300",
    processing: "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300",
    ingesting: "bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300",
    processing_failed: "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300",
    pending: "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300",
    aborted: "bg-zinc-100 text-zinc-700 dark:bg-zinc-900/50 dark:text-zinc-300",
    quarantined: "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300",
  };
  const label: Record<DocVersion["status"], string> = {
    available: "Ready",
    uploaded: "Uploaded",
    security_pending: "Security Pending",
    security_running: "Security Running",
    security_failed: "Security Failed",
    processing: "Processing",
    ingesting: "Ingesting",
    processing_failed: "Processing Failed",
    pending: "Uploading",
    aborted: "Aborted",
    quarantined: "Quarantined",
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
    security_pending: "bg-sky-500",
    security_running: "bg-violet-500",
    security_failed: "bg-red-500",
    processing: "bg-violet-500",
    ingesting: "bg-violet-500",
    processing_failed: "bg-red-500",
    pending: "bg-amber-400",
    aborted: "bg-zinc-300 dark:bg-zinc-600",
    quarantined: "bg-red-500",
  };
  return <span className={`absolute -left-[21px] size-2.5 rounded-full border-2 border-zinc-50 dark:border-zinc-900 ${map[status]}`} />;
}

function hasErrorDetail(status: DocVersion["status"]) {
  return status === "security_failed" || status === "quarantined" || status === "processing_failed" || status === "aborted";
}

/** Split a stored failure reason into readable, formatted lines. */
function formatFailureReason(reason: string): { title: string; details: string[] } {
  // Worker format: "<Reason> (failed: check1, check2)"
  const match = reason.match(/^(.*?)\s*\(failed:\s*([\s\S]+)\)\s*$/);
  if (match) {
    const checks = match[2].split(",").map((c) => c.trim()).filter(Boolean);
    return { title: match[1].trim(), details: checks.map((c) => `Failed check: ${c}`) };
  }
  // Semicolon-joined details ("k: v; k2: v2")
  if (reason.includes("; ")) {
    const [first, ...rest] = reason.split("; ");
    return { title: first.trim(), details: rest.map((r) => r.trim()) };
  }
  return { title: reason.trim(), details: [] };
}

function FailureDetailDialog({
  open,
  versionId,
  status,
  reason,
  onClose,
}: {
  open: boolean;
  versionId: string;
  status: DocVersion["status"];
  reason: string | null | undefined;
  onClose: () => void;
}) {
  const { title, details } = formatFailureReason(reason || "No failure details were recorded for this version.");
  const isInfected = /malware|antivirus/i.test(title);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <ShieldAlert className="size-5 text-red-600 dark:text-red-400" />
          Security check details
        </DialogTitle>
        <DialogDescription>
          Version {versionId.slice(0, 8)} · {statusBadge(status)}
        </DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
      <div className="space-y-4">
        <div className="rounded-xl border border-red-200 bg-red-50/60 p-4 dark:border-red-900/50 dark:bg-red-950/30">
          <p className="text-[11px] font-medium uppercase tracking-wider text-red-500 dark:text-red-400">
            {isInfected ? "Threat detected" : "Failure reason"}
          </p>
          <p className="mt-1.5 text-sm font-medium text-red-800 dark:text-red-200">{title}</p>
        </div>
        {details.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">Details</p>
            <ul className="space-y-1">
              {details.map((d, i) => (
                <li key={i} className="flex items-start gap-2 rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300">
                  <span className="mt-1 size-1.5 shrink-0 rounded-full bg-zinc-400" />
                  <span className="font-mono">{d}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="rounded-lg bg-zinc-50 px-3 py-2.5 text-xs text-zinc-500 dark:bg-zinc-800/40 dark:text-zinc-400">
          This file was not promoted to your knowledge base. Upload a corrected version as a new version of this document.
        </div>
        <div className="flex justify-end">
          <Button variant="outline" onClick={onClose}>Close</Button>
        </div>
      </div>
    </Dialog>
  );
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
      onClose(); // Ensure dialog closes on success
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete document";
      setError(msg);
      // Auto-close on "not found" errors to prevent stuck dialogs
      if (msg.toLowerCase().includes("not found") || msg.toLowerCase().includes("404")) {
        onClose();
      }
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
      onClose(); // Ensure dialog closes on success
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete version";
      setError(msg);
      // Auto-close on "not found" errors to prevent stuck dialogs
      if (msg.toLowerCase().includes("not found") || msg.toLowerCase().includes("404")) {
        onClose();
      }
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
  const [existingDocs, setExistingDocs] = useState<{ documentId: string; name: string; mediaTypes: string[] }[]>([]);
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
    apiFetch<{ documents: { documentId: string; name: string; mediaTypes: string[] }[] }>(
      `/document/global?page=1&pageSize=100`
    )
      .then((res) => setExistingDocs(res.documents))
      .catch(() => setExistingDocs([]));
  }, [open]);

  // Versions of one document must share a media type; only offer
  // same-type documents in the "new version of" dropdown.
  const selectedType = file ? mediaTypeFor(file.name) : null;
  const compatibleDocs = selectedType
    ? existingDocs.filter((d) => d.mediaTypes.length === 0 || d.mediaTypes.includes(selectedType))
    : existingDocs;

  const handleUpload = async () => {
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
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setVersionOf("new"); // re-filter version targets for the new file's type
            }}
          />
          <FileText className="size-6 text-zinc-400" />
          {file ? (
            <span className="text-sm font-medium text-zinc-950 dark:text-zinc-50">{file.name}</span>
          ) : (
            <>
              <span className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                Select a file
              </span>
              <span className="text-xs text-zinc-400">PDF, DOCX, TXT, MD, PNG, HTML or CSV · Max 500 MB</span>
            </>
          )}
        </label>
        <div className="space-y-1.5">
          <Label htmlFor="global-doc-version">Add as</Label>
          <select
            id="global-doc-version"
            value={versionOf}
            onChange={(e) => setVersionOf(e.target.value)}
            className="flex h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-950 shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950/15 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-50 cursor-pointer"
          >
            <option value="new">New document</option>
            {compatibleDocs.map((d) => (
              <option key={d.documentId} value={d.documentId}>
                New version of: {d.name}
              </option>
            ))}
          </select>
          {file && versionOf !== "new" && (
            <p className="text-xs text-zinc-400">
              Showing only documents of the same type ({selectedType}) — versions must match the document's type.
            </p>
          )}
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
  // Version deletes track their parent document too - confirmVersionId alone
  // is not enough to build the DELETE URL.
  const [confirmVersion, setConfirmVersion] = useState<{ documentId: string; versionId: string } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [detailVersion, setDetailVersion] = useState<{ v: DocVersion; docName: string } | null>(null);

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<GlobalDocumentsResponse>(
        `/document/global?page=${p}&pageSize=${PAGE_SIZE}`
      );
      setDocs(res.documents);
      setTotal(res.total);
      // Clamp: if the dataset shrank (deletes by us or others) and the
      // requested page no longer exists, fall back to the last valid page.
      const maxPage = Math.max(1, Math.ceil(res.total / PAGE_SIZE));
      if (res.documents.length === 0 && res.total > 0 && p > maxPage) {
        setLoading(false);
        return load(maxPage);
      }
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
    if (!confirmVersion) return;
    setDeleting(true);
    apiFetch(`/document/${confirmVersion.documentId}/versions/${confirmVersion.versionId}`, { method: "DELETE" })
      .then(() => {
        setConfirmDocId(null);
        setConfirmVersion(null);
        load(page);
      })
      .catch((err) => alert(err instanceof Error ? err.message : "Delete failed"))
      .finally(() => setDeleting(false));
  }, [confirmVersion, page, load]);

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
                  <tr className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer">
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
                          className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 cursor-pointer"
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
                            className="size-7 text-zinc-400 hover:text-red-600 dark:hover:text-red-400 cursor-pointer"
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
                                    {v.fileSize !== null && ` · ${formatFileSize(v.fileSize)}`}
                                  </p>
                                </div>
                                {(v.status === "available" || v.status === "uploaded" || v.status === "security_pending" || v.status === "security_running") && (
                                  <DownloadButton
                                    documentId={doc.documentId}
                                    versionId={v.versionId}
                                    fileName={doc.name}
                                    disabled={deleting}
                                  />
                                )}
                                {hasErrorDetail(v.status) && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="size-7 text-red-400 hover:text-red-600 dark:hover:text-red-300 cursor-pointer"
                                    onClick={() => setDetailVersion({ v, docName: doc.name })}
                                    aria-label="Security check details"
                                  >
                                    <Info className="size-3.5" />
                                  </Button>
                                )}
                                {confirmVersion?.versionId === v.versionId ? (
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
                                    <Button variant="ghost" size="sm" onClick={() => setConfirmVersion(null)}>
                                      Cancel
                                    </Button>
                                  </span>
                                ) : (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="size-7 text-zinc-400 hover:text-red-600 dark:hover:text-red-400"
                                    onClick={() => setConfirmVersion({ documentId: doc.documentId, versionId: v.versionId })}
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
      {confirmVersion && (
        <DeleteVersionDialog
          open
          documentId={confirmVersion.documentId}
          versionId={confirmVersion.versionId}
          docName={docs.find((d) => d.documentId === confirmVersion.documentId)?.name ?? ""}
          onClose={() => setConfirmVersion(null)}
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
      {detailVersion && (
        <FailureDetailDialog
          open
          versionId={detailVersion.v.versionId}
          status={detailVersion.v.status}
          reason={detailVersion.v.quarantineReason}
          onClose={() => setDetailVersion(null)}
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