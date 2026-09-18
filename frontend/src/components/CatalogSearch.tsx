"use client";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";
import { EMPTY_FILTERS, type CatalogFilters, type CatalogMetadata } from "@/hooks/useCatalog";

export function CatalogSearch({ filters, metadata, disabled, onChange, onSearch }: {
  filters: CatalogFilters; metadata: CatalogMetadata; disabled: boolean;
  onChange: (filters: CatalogFilters) => void; onSearch: (filters: CatalogFilters) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const count = [filters.category, filters.brand, filters.maxPrice, filters.minRating, filters.shippingDays, !filters.availableOnly].filter(Boolean).length;
  function update(patch: Partial<CatalogFilters>) { onChange({ ...filters, ...patch }); }
  return <form className="catalog-search" onSubmit={(event) => { event.preventDefault(); onSearch(filters); }}>
    <div className="search-row">
      <label className="search-input-wrap"><Search size={21} /><span className="sr-only">Search products</span><input type="search" value={filters.query} onChange={(event) => update({ query: event.target.value })} placeholder="What are you looking for?" maxLength={2000} /></label>
      <button type="button" className={"filter-toggle " + (expanded ? "is-active" : "")} onClick={() => setExpanded(!expanded)} aria-expanded={expanded} aria-controls="catalog-filters"><SlidersHorizontal size={17} /><span>Filters</span>{count > 0 && <b>{count}</b>}</button>
      <button className="primary search-submit" disabled={disabled}><Search size={16} /><span>{disabled ? "Searching…" : "Search"}</span></button>
    </div>
    {expanded && <div className="filter-panel" id="catalog-filters">
      <label>Category<select value={filters.category} onChange={(event) => update({ category: event.target.value, brand: "" })}><option value="">All categories</option>{metadata.categories.map((category) => <option key={category}>{category}</option>)}</select></label>
      <label>Brand<select value={filters.brand} onChange={(event) => update({ brand: event.target.value })}><option value="">All brands</option>{metadata.brands.map((brand) => <option key={brand}>{brand}</option>)}</select></label>
      <label>Maximum price<div className="price-input"><span>$</span><input aria-label="Maximum price" type="number" min="0.01" step="0.01" max="1000000" placeholder="No limit" value={filters.maxPrice} onChange={(event) => update({ maxPrice: event.target.value })} /></div></label>
      <label>Customer rating<select value={filters.minRating} onChange={(event) => update({ minRating: event.target.value })}><option value="">Any rating</option><option value="4.5">4.5 stars & up</option><option value="4">4 stars & up</option><option value="3">3 stars & up</option></select></label>
      <label>Delivery time<select value={filters.shippingDays} onChange={(event) => update({ shippingDays: event.target.value })}><option value="">Any time</option><option value="2">Within 2 days</option><option value="3">Within 3 days</option><option value="5">Within 5 days</option></select></label>
      <div className="filter-bottom"><label className="checkbox-label"><input type="checkbox" checked={filters.availableOnly} onChange={(event) => update({ availableOnly: event.target.checked })} />In stock only</label><button type="button" className="text-button" onClick={() => onChange({ ...EMPTY_FILTERS, query: filters.query })}><X size={13} />Reset filters</button><button className="primary" disabled={disabled}>Apply filters</button></div>
    </div>}
  </form>;
}
