"use client";
import { ShieldCheck } from "lucide-react";
import type { Checkout } from "@/types/commerce";
import { Modal } from "./Modal";
import { Totals } from "./CartDrawer";
export function CheckoutModal({
  checkout,
  busy,
  onClose,
  onConfirm,
}: {
  checkout: Checkout;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <Modal title="One last look" onClose={onClose}>
      <div className="checkout-intro">
        <ShieldCheck size={25} />
        <p>Your order is ready for review. Nothing has been ordered yet.</p>
      </div>
      <div className="checkout-items">
        {checkout.snapshot.items.map((item) => (
          <div key={item.id}>
            <span>
              {item.quantity} × {item.product.title}
            </span>
            <strong>${item.line_total}</strong>
          </div>
        ))}
      </div>
      <Totals cart={checkout.snapshot} />
      <p className="confirm-question">Would you like me to place this order?</p>
      <button className="primary full" disabled={busy} onClick={onConfirm}>
        {busy ? "Placing order…" : "Yes, place the order"}
      </button>
      <button className="text-button full" disabled={busy} onClick={onClose}>
        Keep shopping
      </button>
      <p className="fine-print">
        Demo checkout · Mock payment only · No card required
        <br />
        Quote expires at{" "}
        {new Date(checkout.expires_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}
        .
      </p>
    </Modal>
  );
}
