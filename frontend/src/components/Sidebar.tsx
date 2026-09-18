"use client";
import { useEffect, useRef } from "react";
import { ArrowUpRight, Bookmark, ChevronLeft, CircleHelp, Headphones, House, Menu, MessageSquare, Package, Search, Settings2, Shirt, ShoppingBag, Smartphone, Sparkles, Trees, X } from "lucide-react";

export type View = "discover" | "chat" | "saved";
export const CATEGORIES = [
  { label: "Electronics", value: "Electronics", icon: Headphones },
  { label: "Home & kitchen", value: "Home and Kitchen", icon: House },
  { label: "Clothing & shoes", value: "Clothing Shoes and Jewelry", icon: Shirt },
  { label: "Beauty & care", value: "Beauty and Personal Care", icon: Sparkles },
  { label: "Sports & outdoors", value: "Sports and Outdoors", icon: Trees },
  { label: "Phones & accessories", value: "Cell Phones and Accessories", icon: Smartphone },
];

export function Sidebar({ view, category, savedCount, collapsed, mobileOpen, busy, recentChat, onNavigate, onCategory, onOrders, onPreferences, onCollapse, onClose, onNewChat }: {
  view: View;
  category: string;
  savedCount: number;
  collapsed: boolean;
  mobileOpen: boolean;
  busy: boolean;
  recentChat?: string;
  onNavigate: (view: View) => void;
  onCategory: (category: string) => void;
  onOrders: () => void;
  onPreferences: () => void;
  onCollapse: () => void;
  onClose: () => void;
  onNewChat: () => void;
}) {
  const mobileDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = mobileDialog.current;
    if (mobileOpen) dialog?.showModal();
    else dialog?.close();
  }, [mobileOpen]);

  const content = <>
    <div className="sidebar-brand">
      <button className="brand-link" onClick={() => onNavigate("discover")} aria-label="ShopPilot home">
        <span className="logo-mark"><ShoppingBag size={23} strokeWidth={1.8} /><span /></span>
        <span className="brand-wordmark">ShopPilot<span>Discover. Compare. Decide.</span></span>
      </button>
      <button className="sidebar-collapse desktop-only" onClick={onCollapse} aria-label={collapsed ? "Expand menu" : "Collapse menu"}><ChevronLeft size={17} /></button>
      <button className="sidebar-collapse mobile-only" onClick={onClose} aria-label="Close menu"><X size={20} /></button>
    </div>
    <div className="sidebar-scroll">
      <p className="nav-caption">YOUR WORKSPACE</p>
      <nav className="sidebar-nav" aria-label="Main navigation">
        {([
          { id: "discover", label: "Discover", icon: Search },
          { id: "chat", label: "AI assistant", icon: MessageSquare },
          { id: "saved", label: "Saved finds", icon: Bookmark },
        ] as const).map(({ id, label, icon: Icon }) => <button key={id} className={"nav-item " + (view === id ? "active" : "")} aria-current={view === id ? "page" : undefined} onClick={() => onNavigate(id)} title={label}>
          <Icon size={18} /><span>{label}</span>{id === "saved" && savedCount > 0 && <b>{savedCount}</b>}
        </button>)}
        <button className="nav-item" onClick={onOrders} disabled={busy} title="My orders"><Package size={18} /><span>My orders</span></button>
      </nav>
      <div className="sidebar-categories">
        <p className="nav-caption">EXPLORE CATEGORIES</p>
        <nav className="sidebar-nav" aria-label="Product categories">
          {CATEGORIES.map(({ label, value, icon: Icon }) => <button key={value} className={"nav-item " + (view === "discover" && category === value ? "category-active" : "")} disabled={busy} onClick={() => onCategory(value)} title={label}>
            <Icon size={17} /><span>{label}</span>
          </button>)}
        </nav>
      </div>
      <div className="sidebar-recents">
        <p className="nav-caption">YOUR CONVERSATION</p>
        {recentChat ? <button className="recent-chat" onClick={() => onNavigate("chat")} title={recentChat}><MessageSquare size={14} /><span>{recentChat}</span></button> : <p className="sidebar-hint">Great finds start with a question.</p>}
        <button className="new-chat" onClick={onNewChat} disabled={busy}>Start a new chat <ArrowUpRight size={13} /></button>
      </div>
    </div>
    <div className="sidebar-bottom">
      <div className="pilot-note"><span className="pilot-note-icon"><Sparkles size={18} /></span><div><strong>A little help from Pilot</strong><p>Your taste. Your budget. Your call.</p></div></div>
      <button className="nav-item" onClick={onPreferences} title="Preferences"><Settings2 size={18} /><span>Preferences</span></button>
      <div className="sidebar-account"><span className="account-avatar">A</span><div><strong>Your shopping space</strong><span>Make yourself at home</span></div><CircleHelp size={16} /></div>
    </div>
  </>;
  return <>
    <aside className={"sidebar " + (collapsed ? "is-collapsed" : "")}>
      {collapsed && <button className="expand-menu" onClick={onCollapse} aria-label="Expand menu"><Menu size={19} /></button>}
      {content}
    </aside>
    <dialog ref={mobileDialog} className="sidebar mobile-sidebar" aria-label="Navigation menu" onCancel={(event) => { event.preventDefault(); onClose(); }} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="mobile-sidebar-content">{content}</div>
    </dialog>
  </>;
}
