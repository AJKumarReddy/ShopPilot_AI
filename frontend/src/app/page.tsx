"use client";
import { ArrowUpRight, Check, Package, ShoppingBag, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CatalogSearch } from "@/components/CatalogSearch";
import { CartDrawer } from "@/components/CartDrawer";
import { ChatPanel } from "@/components/ChatPanel";
import { CheckoutModal } from "@/components/CheckoutModal";
import { ComparisonModal } from "@/components/ComparisonModal";
import { Modal } from "@/components/Modal";
import { ProductCard } from "@/components/ProductCard";
import { Sidebar, type View } from "@/components/Sidebar";
import { useCatalog } from "@/hooks/useCatalog";
import { useSavedProducts } from "@/hooks/useSavedProducts";
import { useTheme } from "@/hooks/useTheme";
import { useVoice } from "@/hooks/useVoice";
import { api, setAccountToken, streamChat } from "@/services/api";
import type { Cart, ChatMessage, ChatResponse, Checkout, Order, Product } from "@/types/commerce";

export default function Page() {
  const catalog = useCatalog();
  const { saved, toggleSaved } = useSavedProducts();
  const { theme, toggleTheme } = useTheme();
  const [view, setView] = useState<View>("discover");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string>();
  const [cart, setCart] = useState<Cart | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [comparison, setComparison] = useState<Product[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [authRequired, setAuthRequired] = useState(false);
  const [token, setToken] = useState("");
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [brands, setBrands] = useState("");
  const busyRef = useRef(false);
  const voice = useVoice((text) => void send(text), setError);

  useEffect(() => { api<{ auth_mode: string }>("/config").then((config) => setAuthRequired(config.auth_mode === "token")).catch(() => setError("Your account settings are unavailable. Please try again.")); }, []);
  async function refreshCart() { const data = await api<Cart>("/cart"); setCart(data); return data; }
  function addMessage(role: "assistant" | "user", content: string) { setMessages((previous) => [...previous, { id: crypto.randomUUID(), role, content }]); }
  function applyResponse(result: ChatResponse) { setSessionId(result.session_id); addMessage("assistant", result.message); if (result.products) { catalog.showRecommendations(result.products); setSelected([]); setView("discover"); } if (result.comparison) setComparison(result.comparison); if (result.cart) { setCart(result.cart); setNotice("Your bag is up to date."); } if (result.checkout) { setCheckout(result.checkout); setCartOpen(false); } if (result.order) { setOrder(result.order); setCheckout(null); void refreshCart(); } voice.speak(result.message); }
  async function action(operation: () => Promise<void>) { if (busyRef.current) return; busyRef.current = true; setBusy(true); setError(""); try { await operation(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Something went wrong. Please try again."); } finally { busyRef.current = false; setBusy(false); setStatus(""); } }
  async function send(text: string) { if (busyRef.current || !text.trim()) return; voice.cancel(); await action(async () => { addMessage("user", text); applyResponse(await streamChat(text, sessionId, setStatus)); }); }
  function startNewChat() { setMessages([]); setSessionId(undefined); setView("chat"); }
  async function addProduct(product: Product) { await action(async () => { setCart(await api<Cart>("/cart/items", { method: "POST", body: JSON.stringify({ product_id: product.id, quantity: 1 }) })); setNotice("Added to your bag."); }); }
  async function prepareCheckout() { await action(async () => { setCheckout(await api<Checkout>("/checkout/prepare", { method: "POST" })); setCartOpen(false); }); }
  async function confirmOrder() { if (!checkout) return; await action(async () => { const result = await api<Order>("/checkout/confirm", { method: "POST", body: JSON.stringify({ checkout_session_id: checkout.id, confirmation_token: checkout.confirmation_token, confirmed: true, idempotency_key: checkout.id }) }); setOrder(result); setCheckout(null); addMessage("assistant", `Your order is confirmed. Total: $${result.total}.`); await refreshCart(); }); }
  async function compareSelected() { await action(async () => { const data = await api<{ products: Product[] }>("/products/compare", { method: "POST", body: JSON.stringify({ product_ids: selected }) }); setComparison(data.products); }); }
  async function showOrders() { await action(async () => { const data = await api<{ orders: Order[] }>("/orders"); if (data.orders.length) setOrder(data.orders[0]); else setNotice("You haven't placed an order yet."); }); }
  const cartCount = cart?.items.reduce((sum, item) => sum + item.quantity, 0) || 0;
  const visibleProducts = view === "saved" ? saved : catalog.products;
  return <>
    <header className="mobile-topbar"><button className="mobile-menu-button" onClick={() => setMobileNav(true)} aria-label="Open navigation">☰</button><span className="mobile-wordmark">ShopPilot <small>SHOP SMARTER</small></span><button className="mobile-cart-button" onClick={() => void action(async () => { await refreshCart(); setCartOpen(true); })} aria-label={`Open shopping bag, ${cartCount} items`}><ShoppingBag size={18} /><b>{cartCount}</b></button></header>
    <Sidebar view={view} category={catalog.applied.category} savedCount={saved.length} collapsed={sidebarCollapsed} mobileOpen={mobileNav} busy={busy} recentChat={messages.at(-1)?.content} onNavigate={(next) => { setView(next); setMobileNav(false); }} onCategory={(category) => { setView("discover"); void catalog.search({ ...catalog.filters, category, brand: "" }); setMobileNav(false); }} onOrders={() => { void showOrders(); setMobileNav(false); }} onPreferences={() => setPreferencesOpen(true)} onCollapse={() => setSidebarCollapsed(!sidebarCollapsed)} onClose={() => setMobileNav(false)} onNewChat={() => { startNewChat(); setMobileNav(false); }} />
    <main className={"store-shell " + (sidebarCollapsed ? "sidebar-collapsed" : "")}>
      <header className="store-header"><div className="store-header-copy"><span className="section-kicker">THE SHOPPILOT EDIT</span><h1>{view === "saved" ? "Your saved finds" : view === "chat" ? "Shop with a little help" : "Find what fits your life."}</h1><p>{view === "saved" ? "A considered shortlist, ready whenever you are." : view === "chat" ? "Tell Pilot what matters and build your shortlist together." : "Search products by the details that matter to you."}</p></div><div className="header-actions"><button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle color theme">{theme === "light" ? "☾" : "☀"}</button><button className="header-orders" onClick={() => void showOrders()}><Package size={16} />Orders</button><button className="bag-button" onClick={() => void action(async () => { await refreshCart(); setCartOpen(true); })} aria-label={`Open shopping bag, ${cartCount} items`}><ShoppingBag size={18} /><span>Bag</span><b>{cartCount}</b></button></div></header>
      {view === "discover" && <CatalogSearch filters={catalog.filters} metadata={catalog.metadata} disabled={catalog.loading || busy} onChange={catalog.setFilters} onSearch={(filters) => void catalog.search(filters)} />}
      {(error || catalog.error) && <div className="error-banner" role="alert">{error || catalog.error}<button onClick={() => { setError(""); catalog.setError(""); }} aria-label="Dismiss error"><X size={16} /></button></div>}
      {notice && <div className="notice" role="status"><Check size={15} />{notice}<button onClick={() => setNotice("")} aria-label="Dismiss notification"><X size={14} /></button></div>}
      {view === "chat" && <div className="chat-page-wrap"><ChatPanel messages={messages} busy={busy} status={status} voice={voice} onSend={(text) => void send(text)} onNewChat={startNewChat} onViewProducts={() => setView("discover")} /></div>}
      {view !== "chat" && <section className="catalog-area"><div className="catalog-toolbar"><div><span className="section-kicker">{view === "saved" ? "SAVED FOR LATER" : "CURATED RESULTS"}</span><h2>{view === "saved" ? `${saved.length} saved ${saved.length === 1 ? "find" : "finds"}` : `${catalog.products.length} products selected for you`}</h2></div><span className="catalog-status"><span /> Metadata matched</span></div>{catalog.loading ? <div className="product-grid">{[0, 1, 2, 3].map((i) => <div className="skeleton-card" key={i} />)}</div> : visibleProducts.length ? <div className="product-grid">{visibleProducts.map((product, index) => <ProductCard key={product.id} product={product} rank={index + 1} selected={selected.includes(product.id)} disabled={busy} onAdd={() => void addProduct(product)} onSave={() => toggleSaved(product)} saved={saved.some((item) => item.id === product.id)} onCompare={() => setSelected((current) => current.includes(product.id) ? current.filter((id) => id !== product.id) : [...current, product.id].slice(0, 5))} />)}</div> : <div className="empty-state"><Sparkles size={38} /><h3>{view === "saved" ? "Nothing saved yet" : "No exact matches"}</h3><p>{view === "saved" ? "Tap the bookmark on a product to keep it here." : "Try widening a filter or asking Pilot for another direction."}</p></div>}</section>}
      {selected.length > 0 && <div className="compare-bar"><span>{selected.length} selected</span><button className="primary" disabled={selected.length < 2 || busy} onClick={() => void compareSelected()}>Compare options <ArrowUpRight size={15} /></button><button className="text-button" onClick={() => setSelected([])}>Clear</button></div>}
      {view === "discover" && <button className="pilot-fab" onClick={() => setView("chat")}><Sparkles size={17} />Ask Pilot <ArrowUpRight size={15} /></button>}
      <footer className="store-footer"><span>ShopPilot · Thoughtful shopping, made easier.</span><span>Secure checkout · You stay in control</span></footer>
    </main>
    {cartOpen && <CartDrawer cart={cart} busy={busy} onClose={() => setCartOpen(false)} onQuantity={(id, quantity) => void action(async () => setCart(await api<Cart>(`/cart/items/${id}`, { method: "PATCH", body: JSON.stringify({ quantity }) })))} onRemove={(id) => void action(async () => setCart(await api<Cart>(`/cart/items/${id}`, { method: "DELETE" })))} onCheckout={() => void prepareCheckout()} />}
    {checkout && <CheckoutModal checkout={checkout} busy={busy} onClose={() => setCheckout(null)} onConfirm={() => void confirmOrder()} />}
    {comparison && <ComparisonModal products={comparison} onClose={() => setComparison(null)} />}
    {order && <Modal title="Your order" onClose={() => setOrder(null)}><div className="order-success"><span><Check size={28} /></span><h3>Order confirmed.</h3><p>Your order is {order.status.toLowerCase()}.</p></div><p className="order-id">Order {order.id}</p>{order.items.map((item) => <div className="order-line" key={item.product_id}><span>{item.quantity} × {item.title}</span></div>)}<div className="grand-total order-total"><span>Total</span><strong>${order.total}</strong></div><p className="fine-print">Your order is ready to be processed.</p><button className="primary full" onClick={() => setOrder(null)}>Continue shopping</button></Modal>}
    {preferencesOpen && <Modal title="Shopping preferences" onClose={() => setPreferencesOpen(false)}><p className="muted">Save brands you return to often.</p><label className="form-label">Favorite brands<input value={brands} onChange={(event) => setBrands(event.target.value)} placeholder="Sony, Adidas, …" maxLength={300} /></label><button className="primary full" onClick={() => void action(async () => { await api("/preferences", { method: "PUT", body: JSON.stringify({ favorite_brands: brands.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 10) }) }); setPreferencesOpen(false); setNotice("Your preferences are saved."); })}>Save preferences</button></Modal>}
    {authRequired && <Modal title="Welcome to ShopPilot" onClose={() => setAuthRequired(false)}><p className="muted">Enter your account access token to continue.</p><form onSubmit={(event) => { event.preventDefault(); setAccountToken(token); void action(async () => { await refreshCart(); setAuthRequired(false); setToken(""); }); }}><label className="form-label">Account access token<input type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} required /></label><button className="primary full" disabled={busy}>Continue</button></form></Modal>}
  </>;
}
