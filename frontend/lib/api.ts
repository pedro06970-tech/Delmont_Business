export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type UserRole = "admin" | "collaborator";

export type User = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Store = {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ConsentEvent = {
  id: string;
  action: "granted" | "revoked";
  source: string | null;
  performed_by_user_id: string;
  occurred_at: string;
};

export type Customer = {
  id: string;
  store_id: string;
  name: string;
  phone_e164: string;
  notes: string | null;
  is_active: boolean;
  has_consent: boolean;
  consented_at: string | null;
  consent_source: string | null;
  consent_revoked_at: string | null;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type CustomerDetail = Customer & { consent_history: ConsentEvent[] };

export type CustomerPage = {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type MessageTemplate = {
  id: string;
  store_id: string;
  name: string;
  content: string;
  is_active: boolean;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type ReminderStatus = "pending" | "cancelled" | "completed" | "failed";

export type Reminder = {
  id: string;
  store_id: string;
  customer_id: string;
  message_template_id: string;
  product_interest: string;
  scheduled_for: string;
  rendered_message: string;
  status: ReminderStatus;
  created_by_user_id: string;
  cancelled_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type ReminderPage = {
  items: Reminder[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const entry = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("delmont_csrf="));
  return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : undefined;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && path !== "/auth/login") {
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      response.status,
      body?.error?.code ?? "request_failed",
      body?.error?.message ?? "Não foi possível concluir a operação.",
    );
  }
  return body as T;
}
