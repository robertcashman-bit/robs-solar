import { z } from "zod";

export const userRoleSchema = z.enum(["admin", "viewer"]);

export const userInfoSchema = z.object({
  username: z.string(),
  role: userRoleSchema,
});

export const loginResponseSchema = z.object({
  user: userInfoSchema,
  csrf_token: z.string(),
});

export const sessionResponseSchema = z.object({
  user: userInfoSchema,
  csrf_token: z.string(),
});

export const magicCodeStatusSchema = z.object({
  enabled: z.boolean(),
  password_login_enabled: z.boolean().optional(),
  email_delivery_configured: z.boolean().optional(),
  dev_delivery: z.boolean().optional(),
});

export const magicCodeRequestResponseSchema = z.object({
  ok: z.boolean(),
  message: z.string(),
  expires_in_seconds: z.number(),
  delivery: z.string().optional(),
  dev_code: z.string().nullable().optional(),
  dev_link: z.string().nullable().optional(),
});

export type UserInfo = z.infer<typeof userInfoSchema>;
