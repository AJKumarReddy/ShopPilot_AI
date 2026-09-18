"use client";
import { useEffect, useState } from "react";
import { api } from "@/services/api";
import type { Product } from "@/types/commerce";

const STORAGE_KEY = "shoppilot-saved-products";

export function useSavedProducts() {
  const [saved, setSaved] = useState<Product[]>([]);
  useEffect(() => {
    let active = true;
    try {
      const stored: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (Array.isArray(stored)) {
        const ids = [...new Set(stored.filter((id): id is string => typeof id === "string"))].slice(0, 100);
        void Promise.allSettled(ids.map((id) => api<Product>("/products/" + encodeURIComponent(id))))
          .then((results) => {
            if (active) setSaved(results.flatMap((result) => result.status === "fulfilled" ? [result.value] : []));
          });
      }
    } catch { /* An unavailable or stale local list should not prevent shopping. */ }
    return () => { active = false; };
  }, []);
  function toggleSaved(product: Product) {
    setSaved((current) => {
      const next = current.some((item) => item.id === product.id)
        ? current.filter((item) => item.id !== product.id)
        : [...current, product];
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next.map((item) => item.id))); } catch { /* Session-only saving still works. */ }
      return next;
    });
  }
  return { saved, toggleSaved };
}
