import type { ChatResponse } from "@/types/commerce";
let accountToken = "";
export function setAccountToken(value: string) {
  accountToken = value;
}
function headers(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...(accountToken ? { Authorization: `Bearer ${accountToken}` } : {}),
  };
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { ...headers(), ...init.headers },
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.message === "string"
        ? data.message
        : "Please check your request and try again.",
    );
  return data as T;
}
export async function streamChat(
  message: string,
  sessionId: string | undefined,
  onStatus: (status: string) => void,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch("/api/v1/chat/stream", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  });
  if (!response.ok || !response.body) {
    const error = await response
      .json()
      .catch(() => ({ message: "Unable to connect to ShopPilot." }));
    throw new Error(error.message || "Unable to connect to ShopPilot.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let result: ChatResponse | undefined;
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder
        .decode(value, { stream: !done })
        .replace(/\r\n/g, "\n");
      let boundary: number;
      while ((boundary = pending.indexOf("\n\n")) !== -1) {
        const event = pending.slice(0, boundary);
        pending = pending.slice(boundary + 2);
        const type = event
          .split("\n")
          .find((line) => line.startsWith("event: "))
          ?.slice(7);
        const payload = event
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
          .join("\n");
        if (!payload) continue;
        const data = JSON.parse(payload);
        if (type === "status") onStatus(data.status);
        if (type === "error") throw new Error(data.message);
        if (type === "result") result = data as ChatResponse;
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
  if (!result)
    throw new Error(
      "The connection ended before a response arrived. Please try again.",
    );
  return result;
}
