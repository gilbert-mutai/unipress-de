"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "./icons";
import { Button } from "./ui/button";

export function ThemeToggle({ onHeader = false }: { onHeader?: boolean }) {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      /* ignore */
    }
  };

  return (
    <Button
      variant={onHeader ? "onHeader" : "ghost"}
      size="icon"
      onClick={toggle}
      aria-label="Toggle theme"
    >
      {dark ? <Moon /> : <Sun />}
    </Button>
  );
}
