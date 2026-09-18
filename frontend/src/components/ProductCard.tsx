"use client";
import { Check, Plus, Star, Truck } from "lucide-react";
import { useState } from "react";
import type { Product } from "@/types/commerce";
export function ProductCard({
  product,
  rank,
  selected,
  disabled,
  onCompare,
  onAdd,
  onSave,
  saved = false,
}: {
  product: Product;
  rank: number;
  selected: boolean;
  disabled: boolean;
  onCompare: () => void;
  onAdd: () => void;
  onSave?: () => void;
  saved?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <article className="product-card" data-testid="product-card">
      <div className="product-image">
        {onSave && <button className={`save-button ${saved ? "is-saved" : ""}`} onClick={onSave} aria-label={`${saved ? "Unsave" : "Save"} ${product.title}`} aria-pressed={saved}>♡</button>}
        <span className={`rank ${rank === 1 ? "top" : ""}`}>
          {rank === 1 ? (
            <>
              <span>✦</span> TOP PICK
            </>
          ) : (
            `#${rank}`
          )}
        </span>
        <label
          className={`compare-check ${selected ? "checked" : ""}`}
          title="Select to compare"
        >
          <input
            aria-label={`Compare ${product.title}`}
            type="checkbox"
            checked={selected}
            onChange={onCompare}
          />
          {selected && <Check size={14} />}
        </label>
        {!failed ? (
          <img
            src={product.image_url}
            alt={product.title}
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setFailed(true)}
          />
        ) : (
          <div className="image-fallback">{product.subcategory}</div>
        )}
      </div>
      <div className="product-details">
        <div className="brand">{product.brand}</div>
        <h3 title={product.title}>{product.title}</h3>
        <div className="rating">
          <Star size={13} fill="currentColor" />{" "}
          <strong>{product.average_rating}</strong>
          <span>({product.rating_count.toLocaleString()})</span>
        </div>
        <div className="price-line">
          <strong>${product.price}</strong>
          {product.original_price !== product.price && (
            <del>${product.original_price}</del>
          )}
        </div>
        <p className="product-reason">
          <span>✦</span>{" "}
          {product.reason ||
            product.features[0] ||
            "Explore this catalog find."}
        </p>
        <div className="shipping">
          <Truck size={13} />
          <span>
            {product.inventory.available
              ? `In stock · ${product.inventory.shipping_days}-day shipping`
              : "Currently unavailable"}
          </span>
        </div>
        <button
          className="add-button"
          onClick={onAdd}
          disabled={disabled || !product.inventory.available}
        >
          <Plus size={15} /> Add to cart
        </button>
      </div>
    </article>
  );
}
