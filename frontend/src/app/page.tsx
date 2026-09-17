"use client";
import Link from "next/link";
import {
  Check,
  ChevronDown,
  Compass,
  Headphones,
  Heart,
  History,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CartDrawer } from "@/components/CartDrawer";
import { ChatPanel } from "@/components/ChatPanel";
import { CheckoutModal } from "@/components/CheckoutModal";
import { ComparisonModal } from "@/components/ComparisonModal";
import { Modal } from "@/components/Modal";
import { ProductCard } from "@/components/ProductCard";
import { useVoice } from "@/hooks/useVoice";
import { api, setAccountToken, streamChat } from "@/services/api";
import type {
  Cart,
  ChatMessage,
  Checkout,
  ChatResponse,
  Order,
  Product,
} from "@/types/commerce";

export default function Page() {
  const [products, setProducts] = useState<Product[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string>();
  const [cart, setCart] = useState<Cart | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [comparison, setComparison] = useState<Product[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mode, setMode] = useState("demo");
  const [authRequired, setAuthRequired] = useState(false);
  const [token, setToken] = useState("");
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [brands, setBrands] = useState("");
  const busyRef = useRef(false);
  const voice = useVoice((text) => void send(text), setError);

  useEffect(() => {
    api<{ ai_mode: string; auth_mode: string }>("/config")
      .then((config) => {
        setMode(config.ai_mode);
        setAuthRequired(config.auth_mode === "token");
      })
      .catch(() =>
        setError("The store is warming up. Please try again in a moment."),
      );
    api<{ products: Product[] }>("/products/search", {
      method: "POST",
      body: JSON.stringify({
        query: "wireless noise cancelling headphones",
        constraints: {
          max_price: 150,
          category: "headphones",
          required_features: ["wireless", "noise cancelling"],
        },
      }),
    })
      .then((data) => setProducts(data.products))
      .catch((error) => setError(error.message))
      .finally(() => setLoading(false));
  }, []);
  async function refreshCart() {
    const data = await api<Cart>("/cart");
    setCart(data);
    return data;
  }
  function addMessage(role: "assistant" | "user", content: string) {
    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), role, content },
    ]);
  }
  function applyResponse(result: ChatResponse) {
    setSessionId(result.session_id);
    addMessage("assistant", result.message);
    if (result.products) {
      setProducts(result.products);
      setSelected([]);
    }
    if (result.comparison) setComparison(result.comparison);
    if (result.cart) {
      setCart(result.cart);
      setNotice("Your shopping bag is up to date.");
    }
    if (result.checkout) {
      setCheckout(result.checkout);
      setCartOpen(false);
    }
    if (result.order) {
      setOrder(result.order);
      setCheckout(null);
      void refreshCart();
    }
    voice.speak(result.message);
  }
  async function action(operation: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      busyRef.current = false;
      setBusy(false);
      setStatus("");
    }
  }
  async function send(text: string) {
    if (busyRef.current || !text.trim()) return;
    voice.cancel();
    await action(async () => {
      addMessage("user", text);
      applyResponse(await streamChat(text, sessionId, setStatus));
    });
  }
  async function addProduct(product: Product) {
    await action(async () => {
      setCart(
        await api<Cart>("/cart/items", {
          method: "POST",
          body: JSON.stringify({ product_id: product.id, quantity: 1 }),
        }),
      );
      setNotice("Added to your shopping bag.");
    });
  }
  async function prepareCheckout() {
    await action(async () => {
      setCheckout(await api<Checkout>("/checkout/prepare", { method: "POST" }));
      setCartOpen(false);
    });
  }
  async function confirmOrder() {
    if (!checkout) return;
    await action(async () => {
      const result = await api<Order>("/checkout/confirm", {
        method: "POST",
        body: JSON.stringify({
          checkout_session_id: checkout.id,
          confirmation_token: checkout.confirmation_token,
          confirmed: true,
          idempotency_key: checkout.id,
        }),
      });
      setOrder(result);
      setCheckout(null);
      addMessage(
        "assistant",
        `Your mock order is confirmed. Total: $${result.total}.`,
      );
      await refreshCart();
    });
  }
  async function compareSelected() {
    await action(async () => {
      const data = await api<{ products: Product[] }>("/products/compare", {
        method: "POST",
        body: JSON.stringify({ product_ids: selected }),
      });
      setComparison(data.products);
    });
  }
  async function showOrders() {
    await action(async () => {
      const data = await api<{ orders: Order[] }>("/orders");
      if (data.orders.length) setOrder(data.orders[0]);
      else setNotice("You haven't placed an order yet.");
    });
  }
  const cartCount =
    cart?.items.reduce((sum, item) => sum + item.quantity, 0) || 0;
  return (
    <>
      <header className="site-header">
        <Link href="/" className="brand-logo">
          <span className="logo-mark">
            <ShoppingBag size={20} />
            <span>✦</span>
          </span>{" "}
          ShopPilot<span className="brand-ai">AI</span>
        </Link>
        <nav aria-label="Main navigation">
          <a className="nav-active" href="#discover">
            Discover
          </a>
          <button onClick={() => void showOrders()}>My orders</button>
        </nav>
        <div className="header-actions">
          <span className="demo-badge">
            <span /> {mode === "demo" ? "DEMO EXPERIENCE" : "AI SHOPPING"}
          </span>
          <button
            className="bag-button"
            onClick={() =>
              void action(async () => {
                await refreshCart();
                setCartOpen(true);
              })
            }
            aria-label={`Open shopping bag, ${cartCount} items`}
          >
            <ShoppingBag size={18} />
            <span>Bag</span>
            <b>{cartCount}</b>
          </button>
          <button
            className="profile-avatar"
            aria-label="Shopping preferences"
            onClick={() => setPreferencesOpen(true)}
          >
            A
          </button>
        </div>
      </header>
      <div className="app-shell">
        <aside className="icon-rail" aria-label="Quick navigation">
          <a
            className="rail-active"
            href="#discover"
            aria-label="Discover products"
          >
            <Compass size={21} />
          </a>
          <button
            aria-label="Preferences"
            onClick={() => setPreferencesOpen(true)}
          >
            <Heart size={21} />
          </button>
          <button aria-label="Order history" onClick={() => void showOrders()}>
            <History size={21} />
          </button>
          <div className="rail-bottom">
            <Headphones size={20} />
          </div>
        </aside>
        <main id="discover">
          <section className="hero">
            <div>
              <div className="eyebrow">
                <Sparkles size={13} /> A LITTLE HELP. A GREAT FIND.
              </div>
              <h1>
                Your next favorite,
                <br className="mobile-break" /> just a conversation away.
              </h1>
              <p>Tell us what matters. We&apos;ll find what fits.</p>
            </div>
            <div className="hero-note">
              <span className="orbit-spark">✦</span>
              <span>
                Thoughtfully picked.
                <br />
                <strong>Always your choice.</strong>
              </span>
            </div>
          </section>
          <div className="shopping-layout">
            <ChatPanel
              messages={messages}
              busy={busy}
              status={status}
              voice={voice}
              onSend={(text) => void send(text)}
            />
            <section
              className="discovery-panel"
              aria-label="Product recommendations"
            >
              <div className="results-heading">
                <div>
                  <span className="eyebrow small">THE DISCOVERY EDIT</span>
                  <h2>
                    {messages.length
                      ? "Picked for your request"
                      : "Find your everyday soundtrack"}
                  </h2>
                  <p>
                    {products.length
                      ? `${products.length} catalog finds, with the details that matter.`
                      : "Your next discovery starts here."}
                  </p>
                </div>
                <button
                  className="filter-button"
                  onClick={() =>
                    void send("Only show products rated above 4.4")
                  }
                  disabled={busy}
                >
                  <SlidersHorizontal size={14} /> Refine{" "}
                  <ChevronDown size={13} />
                </button>
              </div>
              <div className="result-toolbar">
                <span className="collection-pill">
                  <Headphones size={13} />{" "}
                  {messages.length ? "Your recommendations" : "Wireless audio"}
                </span>
                <span>
                  Curated by ShopPilot <Sparkles size={12} />
                </span>
              </div>
              {error && (
                <div className="error-banner" role="alert">
                  {error}
                  <button
                    onClick={() => setError("")}
                    aria-label="Dismiss error"
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
              {notice && (
                <div className="notice" role="status">
                  <Check size={15} />
                  {notice}
                  <button
                    onClick={() => setNotice("")}
                    aria-label="Dismiss notification"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
              {loading ? (
                <div className="product-grid" aria-label="Loading products">
                  {[0, 1, 2].map((i) => (
                    <div className="skeleton-card" key={i} />
                  ))}
                </div>
              ) : products.length ? (
                <div className="product-grid">
                  {products.map((product, index) => (
                    <ProductCard
                      key={product.id}
                      product={product}
                      rank={index + 1}
                      selected={selected.includes(product.id)}
                      disabled={busy}
                      onAdd={() => void addProduct(product)}
                      onCompare={() =>
                        setSelected((current) =>
                          current.includes(product.id)
                            ? current.filter((id) => id !== product.id)
                            : [...current, product.id].slice(0, 5),
                        )
                      }
                    />
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <Compass size={36} />
                  <h3>Let&apos;s try another direction.</h3>
                  <p>
                    Tell ShopPilot a different budget or a few features you can
                    be flexible about.
                  </p>
                </div>
              )}
              {selected.length > 0 && (
                <div className="compare-bar">
                  <span>{selected.length} selected</span>
                  <button
                    className="primary"
                    disabled={selected.length < 2 || busy}
                    onClick={() => void compareSelected()}
                  >
                    Compare options →
                  </button>
                  <button
                    className="text-button"
                    onClick={() => setSelected([])}
                  >
                    Clear
                  </button>
                </div>
              )}
              <div className="discovery-footer">
                <Sparkles size={14} />
                <p>Real catalog details. Clear comparisons. No pressure.</p>
                <span>YOU&apos;RE IN THE PILOT&apos;S SEAT</span>
              </div>
            </section>
          </div>
          <footer className="page-footer">
            <span>ShopPilot AI · A considered way to shop.</span>
            <span>
              Amazon Reviews 2023 catalog · Demo store · Mock checkout
            </span>
          </footer>
        </main>
      </div>
      {cartOpen && (
        <CartDrawer
          cart={cart}
          busy={busy}
          onClose={() => setCartOpen(false)}
          onQuantity={(id, quantity) =>
            void action(async () =>
              setCart(
                await api<Cart>(`/cart/items/${id}`, {
                  method: "PATCH",
                  body: JSON.stringify({ quantity }),
                }),
              ),
            )
          }
          onRemove={(id) =>
            void action(async () =>
              setCart(
                await api<Cart>(`/cart/items/${id}`, { method: "DELETE" }),
              ),
            )
          }
          onCheckout={() => void prepareCheckout()}
        />
      )}
      {checkout && (
        <CheckoutModal
          checkout={checkout}
          busy={busy}
          onClose={() => setCheckout(null)}
          onConfirm={() => void confirmOrder()}
        />
      )}
      {comparison && (
        <ComparisonModal
          products={comparison}
          onClose={() => setComparison(null)}
        />
      )}
      {order && (
        <Modal title="Your order" onClose={() => setOrder(null)}>
          <div className="order-success">
            <span>
              <Check size={28} />
            </span>
            <h3>Good find. It&apos;s confirmed.</h3>
            <p>Your mock order is {order.status.toLowerCase()}.</p>
          </div>
          <p className="order-id">Order {order.id}</p>
          {order.items.map((item) => (
            <div className="order-line" key={item.product_id}>
              <span>
                {item.quantity} × {item.title}
              </span>
            </div>
          ))}
          <div className="grand-total order-total">
            <span>Total</span>
            <strong>${order.total}</strong>
          </div>
          <p className="fine-print">
            This demo does not charge a payment card or ship products.
          </p>
          <button className="primary full" onClick={() => setOrder(null)}>
            Keep discovering
          </button>
        </Modal>
      )}
      {preferencesOpen && (
        <Modal title="Make it yours" onClose={() => setPreferencesOpen(false)}>
          <p className="muted">
            Save useful shopping preferences. Your current request always comes
            first.
          </p>
          <label className="form-label">
            Favorite brands
            <input
              value={brands}
              onChange={(event) => setBrands(event.target.value)}
              placeholder="Sony, Adidas, …"
              maxLength={300}
            />
          </label>
          <button
            className="primary full"
            onClick={() =>
              void action(async () => {
                await api("/preferences", {
                  method: "PUT",
                  body: JSON.stringify({
                    favorite_brands: brands
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean)
                      .slice(0, 10),
                  }),
                });
                setPreferencesOpen(false);
                setNotice("Your preferences are saved.");
              })
            }
          >
            Save preferences
          </button>
        </Modal>
      )}
      {authRequired && (
        <Modal
          title="Welcome to ShopPilot"
          onClose={() => setAuthRequired(false)}
        >
          <p className="muted">
            Enter the demo account access token supplied by the store owner.
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              setAccountToken(token);
              void action(async () => {
                await refreshCart();
                setAuthRequired(false);
                setToken("");
              });
            }}
          >
            <label className="form-label">
              Account access token
              <input
                type="password"
                autoComplete="off"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                required
              />
            </label>
            <button className="primary full" disabled={busy}>
              Continue
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
