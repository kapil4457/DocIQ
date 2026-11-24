"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { Building2, Plus, ChevronDown, ChevronLeft, ChevronRight, Loader2, Mail, Info, Search, KeyRound, Pencil, Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

interface OrganizationRow {
  id: string;
  name: string;
  supportEmail: string;
  memberCount: number;
}

interface PagedOrganizations {
  organizations: OrganizationRow[];
  total: number;
  page: number;
  pageSize: number;
}

const PAGE_SIZE = 8;

export default function ManageOrganizationsPage() {
  const user = useAuth();
  const router = useRouter();
  const [data, setData] = useState<PagedOrganizations | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [detailOrg, setDetailOrg] = useState<OrganizationRow | null>(null);
  const [editOrg, setEditOrg] = useState<OrganizationRow | null>(null);
  const [resetOrg, setResetOrg] = useState<OrganizationRow | null>(null);
  const [createOrgOpen, setCreateOrgOpen] = useState(false);

  useEffect(() => {
    if (user === null) return;
    if (user.role !== "super_admin") router.replace("/");
  }, [user, router]);

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<PagedOrganizations>(`/organization/list?page=${p}&pageSize=${PAGE_SIZE}`);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load organizations");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.role === "super_admin") load(page);
  }, [user, page, load]);

  if (!user || user.role !== "super_admin") {
    return (
      <main className="flex flex-1 items-center justify-center px-4">
        <Loader2 className="size-6 animate-spin text-zinc-400" />
      </main>
    );
  }

  const filtered = data?.organizations.filter((o) =>
    o.name.toLowerCase().includes(search.toLowerCase())
  ) ?? [];
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight">
            <Building2 className="size-6 text-zinc-400" />
            Manage Organizations
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Create organizations. Each one gets an organization super admin whose credentials you can reset on request.
          </p>
        </div>
        <Button onClick={() => setCreateOrgOpen(true)} className="cursor-pointer">
          <Plus className="size-4" />
          New organization
        </Button>
      </div>

      <div className="relative mt-6">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
        <Input
          placeholder="Filter organizations by name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      <div className="mt-5 overflow-hidden rounded-2xl border border-zinc-200/70 bg-white shadow-sm dark:border-zinc-800/70 dark:bg-zinc-900">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="size-6 animate-spin text-zinc-400" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">{error}</p>
            <Button variant="outline" size="sm" onClick={() => load(page)} className="cursor-pointer">Try again</Button>
          </div>
        ) : (
          <Table
            orgs={filtered}
            onShowDetails={setDetailOrg}
            onEdit={setEditOrg}
            onResetCreds={setResetOrg}
          />
        )}
        {!loading && !error && data && data.total > 0 && (
          <div className="flex items-center justify-between border-t border-zinc-200/70 px-4 py-3 dark:border-zinc-800/70">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {data.total} {data.total === 1 ? "organization" : "organizations"}
            </p>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} className="cursor-pointer disabled:cursor-not-allowed">
                <ChevronLeft className="size-4" />
                Prev
              </Button>
              <span className="px-2 text-sm tabular-nums text-zinc-600 dark:text-zinc-300">
                {page} of {totalPages}
              </span>
              <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="cursor-pointer disabled:cursor-not-allowed">
                Next
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      <DetailDialog org={detailOrg} onClose={() => setDetailOrg(null)} />
      <EditDialog org={editOrg} onClose={() => setEditOrg(null)} onSaved={() => load(page)} />
      <ResetCredsDialog org={resetOrg} onClose={() => setResetOrg(null)} />
      <CreateOrgDialog open={createOrgOpen} onClose={() => setCreateOrgOpen(false)} onCreated={() => load(page)} />
    </main>
  );
}

function Table({
  orgs,
  onShowDetails,
  onEdit,
  onResetCreds,
}: {
  orgs: OrganizationRow[];
  onShowDetails: (o: OrganizationRow) => void;
  onEdit: (o: OrganizationRow) => void;
  onResetCreds: (o: OrganizationRow) => void;
}) {
  const [menuOrg, setMenuOrg] = useState<string | null>(null);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const menuBtnRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const openMenu = (orgId: string) => {
    if (menuOrg === orgId) {
      setMenuOrg(null);
      return;
    }
    const btn = menuBtnRefs.current[orgId];
    if (btn) {
      const rect = btn.getBoundingClientRect();
      const menuWidth = 224;
      const left = Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8);
      setMenuPos({ top: rect.bottom + 4, left: Math.max(8, left) });
    }
    setMenuOrg(orgId);
  };

  useEffect(() => {
    if (!menuOrg) return;
    const onScrollOrResize = () => setMenuOrg(null);
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [menuOrg]);

  if (orgs.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <Building2 className="size-8 text-zinc-300 dark:text-zinc-600" />
        <p className="text-sm font-medium">No organizations found</p>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Create the first one to get started.</p>
      </div>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-zinc-200/70 text-left text-xs uppercase tracking-wider text-zinc-400 dark:border-zinc-800/70">
          <th className="px-4 py-3 font-medium">Organization</th>
          <th className="px-4 py-3 font-medium">Members</th>
          <th className="px-4 py-3 text-right font-medium">Actions</th>
        </tr>
      </thead>
      <tbody>
        {orgs.map((org) => (
          <tr
            key={org.id}
            className="border-b border-zinc-100 transition-colors last:border-0 hover:bg-zinc-50/70 dark:border-zinc-800/50 dark:hover:bg-zinc-800/30"
          >
            <td className="px-4 py-3.5">
              <p className="font-medium">{org.name}</p>
              <p className="mt-0.5 flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400">
                <Mail className="size-3" />
                {org.supportEmail}
              </p>
            </td>
            <td className="px-4 py-3.5">
              <Badge>
                {org.memberCount}
              </Badge>
            </td>
            <td className="px-4 py-3.5 text-right">
              <Button
                ref={(el) => { menuBtnRefs.current[org.id] = el; }}
                variant="outline"
                size="sm"
                onClick={() => openMenu(org.id)}
                aria-expanded={menuOrg === org.id}
                className="cursor-pointer"
              >
                Actions
                <ChevronDown className="size-3.5" />
              </Button>
              {menuOrg === org.id && menuPos && (
                <OrgActionMenu
                  org={org}
                  pos={menuPos}
                  onShowDetails={onShowDetails}
                  onEdit={onEdit}
                  onResetCreds={onResetCreds}
                  onClose={() => setMenuOrg(null)}
                />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OrgActionMenu({
  org,
  pos,
  onShowDetails,
  onEdit,
  onResetCreds,
  onClose,
}: {
  org: OrganizationRow;
  pos: { top: number; left: number };
  onShowDetails: (o: OrganizationRow) => void;
  onEdit: (o: OrganizationRow) => void;
  onResetCreds: (o: OrganizationRow) => void;
  onClose: () => void;
}) {
  if (typeof document === "undefined") return null;
  return createPortal(
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        className="fixed z-50 w-56 rounded-xl border border-zinc-200/80 bg-white p-1.5 text-left shadow-lg dark:border-zinc-800 dark:bg-zinc-900 origin-top-right animate-in drop-in duration-200 ease-out-soft"
        style={{ top: pos.top, left: pos.left }}
      >
        {[
          { label: "Show details", icon: Info, action: () => onShowDetails(org) },
          { label: "Edit details", icon: Pencil, action: () => onEdit(org) },
          { label: "Reset admin credentials", icon: KeyRound, action: () => onResetCreds(org) },
        ].map(({ label, icon: Icon, action }) => (
          <button
            key={label}
            onClick={() => {
              onClose();
              action();
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <Icon className="size-4 text-zinc-400" />
            {label}
          </button>
        ))}
      </div>
    </>,
    document.body
  );
}

function CredsReveal({ email, password }: { email: string; password: string }) {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (value: string, key: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(key);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // clipboard refused
    }
  };
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between rounded-xl bg-zinc-50 px-4 py-3 dark:bg-zinc-800/50">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">Email</p>
          <p className="mt-0.5 break-all text-sm font-medium">{email}</p>
        </div>
        <Button variant="ghost" size="icon" className="size-8 cursor-pointer" aria-label="Copy email" onClick={() => copy(email, "email")}>
          {copied === "email" ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4 text-zinc-400" />}
        </Button>
      </div>
      <div className="flex items-center justify-between rounded-xl bg-zinc-50 px-4 py-3 dark:bg-zinc-800/50">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">Temporary password</p>
          <p className="mt-0.5 break-all font-mono text-sm font-medium">{password}</p>
        </div>
        <Button variant="ghost" size="icon" className="size-8 cursor-pointer" aria-label="Copy password" onClick={() => copy(password, "pw")}>
          {copied === "pw" ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4 text-zinc-400" />}
        </Button>
      </div>
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
        Shown only once. Share it through a secure channel; the user will be prompted to keep it safe.
      </p>
    </div>
  );
}

function DetailDialog({ org, onClose }: { org: OrganizationRow | null; onClose: () => void }) {
  return (
    <Dialog open={org !== null} onOpenChange={(o) => !o && onClose()}>
      {org && (
        <>
          <DialogHeader>
            <DialogTitle>{org.name}</DialogTitle>
            <DialogDescription>Organization details</DialogDescription>
          </DialogHeader>
          <DialogClose onClose={onClose} />
          <dl className="space-y-4">
            {[
              ["Organization ID", org.id],
              ["Name", org.name],
              ["Support email", org.supportEmail],
              ["Members", String(org.memberCount)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl bg-zinc-50 px-4 py-3 dark:bg-zinc-800/50">
                <dt className="text-xs font-medium uppercase tracking-wider text-zinc-400">{label}</dt>
                <dd className="mt-1 break-all text-sm font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </Dialog>
  );
}

function EditDialog({
  org,
  onClose,
  onSaved,
}: {
  org: OrganizationRow | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [supportEmail, setSupportEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (org) {
      setName(org.name);
      setSupportEmail(org.supportEmail);
      setError(null);
    }
  }, [org]);

  const submit = async () => {
    if (!org) return;
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/organization/${org.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name, supportEmail }),
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update organization");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={org !== null} onOpenChange={(o) => !o && onClose()}>
      {org && (
        <>
          <DialogHeader>
            <DialogTitle>Edit {org.name}</DialogTitle>
            <DialogDescription>Update the organization&apos;s details.</DialogDescription>
          </DialogHeader>
          <DialogClose onClose={onClose} />
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="eo-name">Organization name</Label>
              <Input id="eo-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="eo-email">Support email</Label>
              <Input id="eo-email" type="email" value={supportEmail} onChange={(e) => setSupportEmail(e.target.value)} />
            </div>
            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>
            )}
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={onClose} className="cursor-pointer">Cancel</Button>
              <Button onClick={submit} disabled={!name.trim() || !supportEmail.trim() || saving} className="cursor-pointer disabled:cursor-not-allowed">
                {saving && <Loader2 className="size-4 animate-spin" />}
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </div>
        </>
      )}
    </Dialog>
  );
}

function ResetCredsDialog({ org, onClose }: { org: OrganizationRow | null; onClose: () => void }) {
  const [confirming, setConfirming] = useState(true);
  const [creds, setCreds] = useState<{ email: string; temporaryPassword: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    if (org) {
      setConfirming(true);
      setCreds(null);
      setError(null);
    }
  }, [org]);

  const reset = async () => {
    if (!org) return;
    setWorking(true);
    setError(null);
    try {
      const res = await apiFetch<{ email: string; temporaryPassword: string }>(
        `/organization/${org.id}/reset-org-admin-credentials`,
        { method: "POST" }
      );
      setCreds(res);
      setConfirming(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset credentials");
    } finally {
      setWorking(false);
    }
  };

  return (
    <Dialog open={org !== null} onOpenChange={(o) => !o && onClose()}>
      {org && (
        <>
          <DialogHeader>
            <DialogTitle>Reset admin credentials</DialogTitle>
            <DialogDescription>
              {confirming
                ? `Generate a new password for the organization super admin of ${org.name}. Their current password stops working immediately.`
                : "New credentials for the organization super admin."}
            </DialogDescription>
          </DialogHeader>
          <DialogClose onClose={onClose} />
          {confirming ? (
            <div className="space-y-4">
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                This replaces the existing password. There is no undo.
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={onClose} className="cursor-pointer">Cancel</Button>
                <Button onClick={reset} disabled={working} className="cursor-pointer disabled:cursor-not-allowed">
                  {working && <Loader2 className="size-4 animate-spin" />}
                  {working ? "Resetting…" : "Reset credentials"}
                </Button>
              </div>
            </div>
          ) : creds ? (
            <CredsReveal email={creds.email} password={creds.temporaryPassword} />
          ) : (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </>
      )}
    </Dialog>
  );
}

function CreateOrgDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [supportEmail, setSupportEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [creds, setCreds] = useState<{ email: string; temporaryPassword: string } | null>(null);

  useEffect(() => {
    if (open) {
      setName("");
      setSupportEmail("");
      setError(null);
      setSubmitting(false);
      setCreds(null);
    }
  }, [open]);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiFetch<{ orgSuperAdminEmail?: string; tempPassword?: string }>("/organization/create", {
        method: "POST",
        body: JSON.stringify({ name, supportEmail }),
      });
      if (res.orgSuperAdminEmail && res.tempPassword) {
        setCreds({ email: res.orgSuperAdminEmail, temporaryPassword: res.tempPassword });
      } else {
        onCreated();
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create organization");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o && !creds) onClose(); }}>
      <DialogHeader>
        <DialogTitle>
          {creds ? "Organization created" : "New organization"}
        </DialogTitle>
        <DialogDescription>
          {creds
            ? "Save these credentials now. They will not be shown again."
            : "An organization super admin account is created automatically."}
        </DialogDescription>
      </DialogHeader>
      <DialogClose onClose={() => { if (!creds) onClose(); else { onCreated(); onClose(); } }} />
      {creds ? (
        <div className="space-y-4">
          <CredsReveal email={creds.email} password={creds.temporaryPassword} />
          <div className="flex justify-end">
            <Button onClick={() => { onCreated(); onClose(); }} className="cursor-pointer">Done</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="co-name">Organization name</Label>
            <Input id="co-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Corp" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="co-email">Support email</Label>
            <Input id="co-email" type="email" value={supportEmail} onChange={(e) => setSupportEmail(e.target.value)} placeholder="support@acme.com" />
            <p className="text-xs text-zinc-400">This becomes the organization super admin&apos;s login email.</p>
          </div>
          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose} className="cursor-pointer">Cancel</Button>
            <Button onClick={submit} disabled={!name.trim() || !supportEmail.trim() || submitting} className="cursor-pointer disabled:cursor-not-allowed">
              {submitting && <Loader2 className="size-4 animate-spin" />}
              {submitting ? "Creating…" : "Create organization"}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
