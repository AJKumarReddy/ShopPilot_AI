"use client";
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

export function useTheme() {
  const [theme, setTheme] = useState<Theme>("light");
  useEffect(() => {
    let initial: Theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    try {
      const saved = localStorage.getItem("shoppilot-theme");
      if (saved === "light" || saved === "dark") initial = saved;
    } catch { /* Browser storage is optional. */ }
    setTheme(initial);
    document.documentElement.dataset.theme = initial;
  }, []);
  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("shoppilot-theme", next); } catch { /* Keep the current session usable. */ }
  }
  return { theme, toggleTheme };
}
