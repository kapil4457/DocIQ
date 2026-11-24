"use client";

import { useSyncExternalStore } from "react";

export interface AuthUser {
  userId: string;
  name: string;
  email: string;
  organizationId: string | null;
  role: "participant" | "org_admin" | "org_super_admin" | "super_admin";
  accessToken?: string;
  refreshToken?: string;
}

const STORAGE_KEY = "dociq.auth.user";

let user: AuthUser | null = null;
let hydrated = false;
const listeners = new Set<() => void>();

function hydrate() {
  if (hydrated) return;
  hydrated = true;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) user = JSON.parse(raw) as AuthUser;
  } catch {
    user = null;
  }
}

function notify() {
  listeners.forEach((l) => l());
}

export function getUser(): AuthUser | null {
  hydrate();
  return user;
}

export function setUser(next: AuthUser | null) {
  user = next;
  hydrated = true;
  try {
    if (next) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // storage unavailable; session-only auth
  }
  notify();
}

export function updateTokens(accessToken: string, refreshToken?: string) {
  if (!user) return;
  setUser({ ...user, accessToken, refreshToken: refreshToken ?? user.refreshToken });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useAuth() {
  return useSyncExternalStore(
    subscribe,
    () => {
      hydrate();
      return user;
    },
    () => null
  );
}

export function canUploadDocuments(user: AuthUser | null): boolean {
  return false;
}
