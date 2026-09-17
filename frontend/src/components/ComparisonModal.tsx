"use client";
import type { Product } from "@/types/commerce";
import { Modal } from "./Modal";
export function ComparisonModal({
  products,
  onClose,
}: {
  products: Product[];
  onClose: () => void;
}) {
  const keys = [
    ...new Set(products.flatMap((p) => Object.keys(p.attributes))),
  ].slice(0, 12);
  function value(product: Product, key: string): string {
    if (key === "Price") return `$${product.price}`;
    if (key === "Rating")
      return `${product.average_rating}/5 (${product.rating_count.toLocaleString()} reviews)`;
    if (key === "Shipping") return `${product.inventory.shipping_days} days`;
    const attribute = product.attributes[key];
    return attribute
      ? Array.isArray(attribute)
        ? attribute.join(", ")
        : attribute
      : "Not listed";
  }
  return (
    <Modal title="A closer look" onClose={onClose}>
      <p className="muted">Compare the details that matter to you.</p>
      <div className="comparison-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Details</th>
              {products.map((p) => (
                <th key={p.id} scope="col">
                  {p.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {["Price", "Rating", "Shipping", ...keys].map((row) => (
              <tr key={row}>
                <th scope="row">{row.replaceAll("_", " ")}</th>
                {products.map((product) => (
                  <td key={product.id}>{value(product, row)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
