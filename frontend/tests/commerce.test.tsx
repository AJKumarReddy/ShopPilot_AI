import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CheckoutModal } from "@/components/CheckoutModal";
import { ProductCard } from "@/components/ProductCard";
import { BrowserVoiceProvider } from "@/lib/voice";
import type { Checkout, Product } from "@/types/commerce";
const product: Product = {
  id: "test-1",
  title: "Stored headphones",
  brand: "Test",
  price: "89.99",
  original_price: "89.99",
  currency: "USD",
  average_rating: "4.5",
  rating_count: 42,
  image_url: "https://example.test/image.jpg",
  description: "Catalog description",
  major_category: "Electronics",
  subcategory: "Headphones",
  product_type: "headphones",
  attributes: {},
  features: [],
  source: "test",
  inventory: {
    available: true,
    stock_quantity: 3,
    shipping_days: 2,
    discount_percentage: "0",
  },
};
describe("commerce UI", () => {
  it("renders stored facts and explicit cart action", () => {
    const add = vi.fn();
    render(
      <ProductCard
        product={product}
        rank={1}
        selected={false}
        disabled={false}
        onCompare={vi.fn()}
        onAdd={add}
      />,
    );
    expect(screen.getByText("$89.99")).toBeInTheDocument();
    expect(screen.getByText("4.5")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(add).toHaveBeenCalledOnce();
  });
  it("never confirms a checkout on render or cancellation", () => {
    const confirm = vi.fn();
    const close = vi.fn();
    const checkout: Checkout = {
      id: "checkout",
      total: "97.41",
      confirmation_token: "opaque",
      expires_at: "2030-01-01T12:00:00Z",
      confirmed: false,
      message: "Confirm?",
      snapshot: {
        id: "cart",
        items: [],
        subtotal: "89.99",
        tax: "7.42",
        discounts: "0",
        total: "97.41",
        currency: "USD",
      },
    };
    render(
      <CheckoutModal
        checkout={checkout}
        busy={false}
        onClose={close}
        onConfirm={confirm}
      />,
    );
    expect(confirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Keep shopping"));
    expect(confirm).not.toHaveBeenCalled();
    expect(close).toHaveBeenCalledOnce();
    fireEvent.click(
      screen.getByRole("button", { name: "Yes, place the order" }),
    );
    expect(confirm).toHaveBeenCalledOnce();
  });
  it("voice gracefully falls back to text", () => {
    const provider = new BrowserVoiceProvider(vi.fn());
    const error = vi.fn();
    expect(provider.supported).toBe(false);
    provider.listen(vi.fn(), error);
    expect(error).toHaveBeenCalledWith(expect.stringContaining("type"));
    provider.dispose();
  });
});
