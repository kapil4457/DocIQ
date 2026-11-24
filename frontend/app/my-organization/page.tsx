"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Users, UserPlus, Trash2, Loader2, ShieldCheck, KeyRound, ChevronLeft, ChevronRight, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

interface OrgUserRow {
  id: string;
  name: string;
  email: string;
  role: "participant" | "org_admin" | "org_super_admin";
}

interface PagedUsers {
  users: OrgUserRow[];
  total: number;
  page: number;
  pageSize: number;
}

const PAGE_SIZE = 8;

export default function MyOrganizationPage() {
  const user = useAuth();
  const router = useRouter();
  const [data, setData] = useState<PagedUsers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [addOpen, setAddOpen] = useState(false);
  const [resetUser, setResetUser] = useState<OrgUserRow | null>(null);
  const [creds, setCreds] = useState<{ email: string; temporaryPassword: string } | null>(null);

  const orgId = user?.organizationId;
  const isOrgSuperAdmin = user?.role === "org_super_admin";

  useEffect(() => {
    if (user === null) return;
    if (!isOrgSuperAdmin || !orgId) router.replace("/");
  }, [user, isOrgSuperAdmin, orgId, router]);

  const load = useCallback(
    async (p: number) => {
      if (!orgId) return;
      setLoading(true);
      setError(null);
      try {
        const res = await apiFetch<PagedUsers>(`/user/organization/${orgId}/users?page=${p}&pageSize=${PAGE_SIZE}`);
        setData(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load users");
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [orgId]
  );

  useEffect(() => {
    if (isOrgSuperAdmin && orgId) load(page);
  }, [isOrgSuperAdmin, orgId, page, load]);

  const toggleRole = async (u: OrgUserRow) => {
    if (!orgId) return;
    const nextRole = u.role === "org_admin" ? "participant" : "org_admin";
    await apiFetch(`/user/organization/${orgId}/users/${u.id}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role: nextRole }),
    });
    load(page);
  };

  const removeUser = async (u: OrgUserRow) => {
    if (!orgId) return;
    await apiFetch(`/user/organization/${orgId}/users/${u.id}`, { method: "DELETE" });
    load(page);
  };

  if (!user || !isOrgSuperAdmin || !orgId) {
    return (
      <main className="flex flex-1 items-center justify-center px-4">
        <Loader2 className="size-6 animate-spin text-zinc-400" />
      </main>
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight">
            <Users className="size-6 text-zinc-400" />
            My Organization
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Add members, promote admins, and manage access for your organization.
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)} className="cursor-pointer">
          <UserPlus className="size-4" />
          Add user
        </Button>
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl border border-zinc-200/70 bg-white shadow-sm dark:border-zinc-800/70 dark:bg-zinc-900">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="size-6 animate-spin text-zinc-400" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">{error}</p>
            <Button variant="outline" size="sm" onClick={() => load(page)} className="cursor-pointer">Try again</Button>
          </div>
        ) : !data || data.users.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-16 text-center">
            <Users className="size-8 text-zinc-300 dark:text-zinc-600" />
            <p className="text-sm font-medium">No members yet</p>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Add your first teammate to get started.</p>
          </div>
        ) : (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800/50">
            {data.users.map((u) => {
              const isSelf = u.id === user.userId;
              const isOrgSuperAdminRow = u.role === "org_super_admin";
              return (
                <li
                  key={u.id}
                  className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-zinc-50/70 dark:hover:bg-zinc-800/30"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-zinc-950/5 text-xs font-semibold text-zinc-600 dark:bg-white/10 dark:text-zinc-300">
                    {u.name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{u.name}</span>
                      {isSelf && <span className="text-xs text-zinc-400">(you)</span>}
                    </span>
                    <span className="block truncate text-xs text-zinc-500 dark:text-zinc-400">{u.email}</span>
                  </span>
                  <Badge className="capitalize">
                    {u.role === "org_admin" && <ShieldCheck className="size-3" />}
                    {u.role === "org_super_admin" && <ShieldCheck className="size-3" />}
                    {u.role.replace(/_/g, " ")}
                  </Badge>
                  {!isSelf && !isOrgSuperAdminRow && (
                    <>
                      <Button variant="ghost" size="sm" onClick={() => toggleRole(u)} title="Toggle between participant and org admin" className="cursor-pointer">
                        {u.role === "org_admin" ? "Demote" : "Promote"}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setResetUser(u)} title="Reset password" className="cursor-pointer">
                        <KeyRound className="size-4 text-zinc-400" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-zinc-400 hover:text-red-600 dark:hover:text-red-400 cursor-pointer"
                        aria-label={`Remove ${u.name}`}
                        onClick={() => removeUser(u)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {!loading && !error && data && data.total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-zinc-200/70 px-4 py-3 dark:border-zinc-800/70">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">{data.total} members</p>
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

      <AddUserDialog
        open={addOpen}
        orgId={orgId}
        onClose={() => setAddOpen(false)}
        onCreated={() => load(page)}
      />

      <Dialog open={resetUser !== null} onOpenChange={(o) => { if (!o) { setResetUser(null); setCreds(null); } }}>
        {resetUser && (
          <>
            <DialogHeader>
              <DialogTitle>Reset credentials</DialogTitle>
              <DialogDescription>
                {creds
                  ? "New credentials. Shown only once."
                  : `Generate a new password for ${resetUser.name}. Their current password stops working immediately.`}
              </DialogDescription>
            </DialogHeader>
            <DialogClose onClose={() => { setResetUser(null); setCreds(null); }} />
            {creds ? (
              <div className="space-y-4">
                <div className="rounded-xl bg-zinc-50 px-4 py-3 dark:bg-zinc-800/50">
                  <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">Email</p>
                  <p className="mt-0.5 text-sm font-medium">{creds.email}</p>
                </div>
                <div className="rounded-xl bg-zinc-50 px-4 py-3 dark:bg-zinc-800/50">
                  <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">Temporary password</p>
                  <p className="mt-0.5 flex items-center gap-2 font-mono text-sm font-medium">
                    {creds.temporaryPassword}
                    <button
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 cursor-pointer"
                      aria-label="Copy password"
                      onClick={async () => {
                        try { await navigator.clipboard.writeText(creds.temporaryPassword); } catch {}
                      }}
                    >
                      <Check className="size-4" />
                    </button>
                  </p>
                </div>
                <div className="flex justify-end">
                  <Button onClick={() => { setResetUser(null); setCreds(null); }} className="cursor-pointer">Done</Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                  This replaces the existing password. There is no undo.
                </p>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setResetUser(null)} className="cursor-pointer">Cancel</Button>
                  <Button
                    onClick={async () => {
                      try {
                        const res = await apiFetch<{ email: string; temporaryPassword: string }>(
                          `/user/organization/${orgId}/users/${resetUser.id}/reset-credentials`,
                          { method: "POST" }
                        );
                        setCreds(res);
                      } catch {}
                    }}
                    className="cursor-pointer"
                  >
                    Reset credentials
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Dialog>
    </main>
  );
}

function AddUserDialog({
  open,
  orgId,
  onClose,
  onCreated,
}: {
  open: boolean;
  orgId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"participant" | "org_admin">("participant");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setEmail("");
      setPassword("");
      setRole("participant");
      setError(null);
    }
  }, [open]);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch(`/user/organization/${orgId}/users`, {
        method: "POST",
        body: JSON.stringify({ name, email, password, role }),
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <DialogTitle>Add user</DialogTitle>
        <DialogDescription>They log in with these credentials. Share the password securely.</DialogDescription>
      </DialogHeader>
      <DialogClose onClose={onClose} />
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="au-name">Full name</Label>
          <Input id="au-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="au-email">Email</Label>
          <Input id="au-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ada@company.com" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="au-password">Temporary password</Label>
          <Input id="au-password" type="text" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" minLength={8} />
        </div>
        <div className="space-y-1.5">
          <Label>Role</Label>
          <div className="grid grid-cols-2 gap-2">
            {(["participant", "org_admin"] as const).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={`rounded-lg border px-3 py-2 text-sm capitalize transition-colors cursor-pointer ${
                  role === r
                    ? "border-zinc-950 bg-zinc-950 text-zinc-50 dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-950"
                    : "border-zinc-200 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                }`}
              >
                {r.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>
        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{error}</p>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" onClick={onClose} className="cursor-pointer">Cancel</Button>
          <Button onClick={submit} disabled={!name.trim() || !email.trim() || password.length < 8 || submitting} className="cursor-pointer disabled:cursor-not-allowed">
            {submitting && <Loader2 className="size-4 animate-spin" />}
            {submitting ? "Creating…" : "Create user"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
