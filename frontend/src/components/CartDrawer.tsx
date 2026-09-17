"use client";
import { Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { Modal } from "./Modal";
import type { Cart } from "@/types/commerce";
export function Totals({ cart }: { cart: Cart }) {
  return (
    <dl className="totals">
      <div>
        <dt>Subtotal</dt>
        <dd>${cart.subtotal}</dd>
      </div>
      <div>
        <dt>Savings included</dt>
        <dd>${cart.discounts}</dd>
      </div>
      <div>
        <dt>Estimated tax</dt>
        <dd>${cart.tax}</dd>
      </div>
      <div className="grand-total">
        <dt>Total</dt>
        <dd>${cart.total}</dd>
      </div>
    </dl>
  );
}
export function CartDrawer({
  cart,
  busy,
  onClose,
  onQuantity,
  onRemove,
  onCheckout,
}: {
  cart: Cart | null;
  busy: boolean;
  onClose: () => void;
  onQuantity: (id: string, quantity: number) => void;
  onRemove: (id: string) => void;
  onCheckout: () => void;
}) {
  return (
    <Modal title="Your shopping bag" onClose={onClose} drawer>
      {!cart?.items.length ? (
        <div className="empty-state">
          <ShoppingBag size={40} />
          <h3>A little room for your next favorite.</h3>
          <p>Ask ShopPilot to find something for you.</p>
        </div>
      ) : (
        <>
          <div className="cart-items">
            {cart.items.map((item) => (
              <article className="cart-item" key={item.id}>
                <img
                  src={item.product.image_url}
                  alt=""
                  referrerPolicy="no-referrer"
                />
                <div>
                  <h3>{item.product.title}</h3>
                  <p>{item.variant}</p>
                  <strong>${item.line_total}</strong>
                  <div className="quantity-controls">
                    <button
                      aria-label={`Decrease quantity of ${item.product.title}`}
                      disabled={busy || item.quantity <= 1}
                      onClick={() => onQuantity(item.id, item.quantity - 1)}
                    >
                      <Minus size={13} />
                    </button>
                    <span>{item.quantity}</span>
                    <button
                      aria-label={`Increase quantity of ${item.product.title}`}
                      disabled={busy || item.quantity >= 99}
                      onClick={() => onQuantity(item.id, item.quantity + 1)}
                    >
                      <Plus size={13} />
                    </button>
                    <button
                      aria-label={`Remove ${item.product.title}`}
                      disabled={busy}
                      onClick={() => onRemove(item.id)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
          <Totals cart={cart} />
          <button className="primary full" disabled={busy} onClick={onCheckout}>
            Review checkout <span>→</span>
          </button>
          <p className="fine-print">
            You&apos;ll review and confirm before an order is placed.
          </p>
        </>
      )}
    </Modal>
  );
}
