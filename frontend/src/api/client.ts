/** Client HTTP minimal pour l'API DataFlow360. */

import type {
  AssistantIn,
  AssistantOut,
  RechercheIn,
  RechercheOut,
} from "../types/api";

const API_BASE = "http://localhost:8001/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  let response: Response;

  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, "API injoignable — vérifier que le service tourne");
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* corps non-JSON, on garde le message par défaut */
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  askAssistant: (payload: AssistantIn) =>
    request<AssistantOut>("/assistant/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  rechercher: (payload: RechercheIn) =>
    request<RechercheOut>("/recherche", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
