import type { UserInfo } from "./schemas";

export function canWrite(user: UserInfo | null): boolean {
  return user?.role === "admin";
}

export function canViewAudit(user: UserInfo | null): boolean {
  return user?.role === "admin";
}
