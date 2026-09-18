"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import type { Product } from "@/types/commerce";

export interface CatalogFilters {
  query: string;
  category: string;
  brand: string;
  maxPrice: string;
  minRating: string;
  shippingDays: string;
  availableOnly: boolean;
  sort: "relevance" | "price_asc" | "rating";
}
export const EMPTY_FILTERS: CatalogFilters = { query: "", category: "", brand: "", maxPrice: "", minRating: "", shippingDays: "", availableOnly: true, sort: "relevance" };
const INITIAL_FILTERS: CatalogFilters = { ...EMPTY_FILTERS, query: "wireless headphones", maxPrice: "150" };
export interface CatalogMetadata { categories: string[]; brands: string[] }

export function useCatalog() {
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [applied, setApplied] = useState(INITIAL_FILTERS);
  const [products, setProducts] = useState<Product[]>([]);
  const [metadata, setMetadata] = useState<CatalogMetadata>({ categories: [], brands: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);

  const search = useCallback(async (next: CatalogFilters) => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    setFilters(next);
    try {
      const result = await api<{ products: Product[] }>("/products/search", {
        method: "POST", signal: controller.signal,
        body: JSON.stringify({ query: next.query, constraints: {
          major_category: next.category || undefined,
          brands: next.brand ? [next.brand] : [],
          max_price: next.maxPrice ? Number(next.maxPrice) : undefined,
          min_rating: next.minRating ? Number(next.minRating) : undefined,
          max_shipping_days: next.shippingDays ? Number(next.shippingDays) : undefined,
          available_only: next.availableOnly,
          sort_preference: next.sort,
        } }),
      });
      if (!controller.signal.aborted) { setProducts(result.products); setApplied(next); }
    } catch (error) {
      if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "Couldn't load the catalog. Please try again.");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => { void search(INITIAL_FILTERS); return () => request.current?.abort(); }, [search]);
  useEffect(() => {
    const controller = new AbortController();
    void api<CatalogMetadata>("/products/metadata" + (filters.category ? "?major_category=" + encodeURIComponent(filters.category) : ""), { signal: controller.signal })
      .then(setMetadata).catch(() => { /* Search remains available if filter options fail. */ });
    return () => controller.abort();
  }, [filters.category]);

  function showRecommendations(recommendations: Product[]) {
    request.current?.abort();
    setProducts(recommendations);
    setLoading(false);
    setError("");
  }
  return { filters, setFilters, applied, products, metadata, loading, error, setError, search, showRecommendations };
}
