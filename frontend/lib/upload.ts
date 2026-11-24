import { sha256 } from "js-sha256";
import { apiFetch } from "./api";

export interface UploadRegisterPayload {
  scope: "global" | "workspace";
  workspaceId?: string;
  documentId?: string | null;
  documentName: string;
  mediaType: string;
  fileSize: number;
}

export interface UploadResult {
  alreadyCompleted: boolean;
  documentId?: string;
  versionId?: string;
}

interface RegisterResponse {
  documentId: string;
  versionId: string;
  upload: { uploadId: string; objectKey: string; chunkSize: number; partUrls: { partNumber: number; url: string }[] };
}

export function createUploadKeyTracker() {
  let current: { name: string; size: number; key: string } | null = null;
  return {
    keyFor(file: File): string {
      if (current && current.name === file.name && current.size === file.size) return current.key;
      const key = crypto.randomUUID();
      current = { name: file.name, size: file.size, key };
      return key;
    },
    reset() {
      current = null;
    },
  };
}

export async function uploadDocument(
  file: File,
  payload: UploadRegisterPayload,
  idempotencyKey: string,
): Promise<UploadResult> {
  let register: RegisterResponse;
  try {
    register = await apiFetch<RegisterResponse>("/document/register/init", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Idempotency-Key": idempotencyKey },
    });
  } catch (err) {
    if (err instanceof Error && err.message.includes("already completed")) {
      return { alreadyCompleted: true };
    }
    throw err;
  }

  const hasher = sha256.create();
  const chunkSize = register.upload.chunkSize * 1024 * 1024;
  const parts: { partNumber: number; etag: string }[] = [];
  for (const part of register.upload.partUrls) {
    const start = (part.partNumber - 1) * chunkSize;
    const end = Math.min(part.partNumber * chunkSize, file.size);
    const chunk = file.slice(start, end);
    hasher.update(await chunk.arrayBuffer());
    const res = await fetch(part.url, { method: "PUT", body: chunk });
    if (!res.ok) throw new Error(`Part ${part.partNumber} upload failed`);
    parts.push({ partNumber: part.partNumber, etag: res.headers.get("ETag") ?? "" });
  }

  await apiFetch(`/document/register/${register.versionId}/complete`, {
    method: "POST",
    body: JSON.stringify({ uploadId: register.upload.uploadId, parts, hash: hasher.hex() }),
  });

  return { alreadyCompleted: false, documentId: register.documentId, versionId: register.versionId };
}

export function mediaTypeFor(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    pdf: "pdf", docx: "docx", txt: "txt", md: "md", png: "png", html: "html", csv: "csv",
  };
  return map[ext] ?? "txt";
}
