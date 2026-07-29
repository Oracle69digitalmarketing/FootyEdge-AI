import { useState, useEffect, useCallback } from "react";
import { ToolId } from "@app/types/toolId";

const RECENT_TOOLS_KEY = "stirlingpdf.recentTools";
const FAVORITE_TOOLS_KEY = "stirlingpdf.favoriteTools";

const DEFAULT_FAVORITES: ToolId[] = [
  "ocr" as ToolId,
  "redact" as ToolId,
  "addText" as ToolId,
  "merge" as ToolId,
  "pdfTextEditor" as ToolId,
  "vectorExport" as ToolId,
];

export function useToolHistory() {
  const [recentTools, setRecentTools] = useState<ToolId[]>([]);
  const [favoriteTools, setFavoriteTools] = useState<ToolId[]>(DEFAULT_FAVORITES);

  // Load from localStorage on mount
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const recentStr = window.localStorage.getItem(RECENT_TOOLS_KEY);
    const favoritesStr = window.localStorage.getItem(FAVORITE_TOOLS_KEY);

    if (recentStr) {
      try {
        const recent = JSON.parse(recentStr) as ToolId[];
        setRecentTools(recent);
      } catch {
        // Ignore parse errors
      }
    }

    if (favoritesStr) {
      try {
        const favorites = JSON.parse(favoritesStr) as ToolId[];
        setFavoriteTools(favorites);
      } catch {
        // Ignore parse errors
      }
    } else {
      // If no favorites in localStorage, save the defaults
      window.localStorage.setItem(
        FAVORITE_TOOLS_KEY,
        JSON.stringify(DEFAULT_FAVORITES),
      );
    }
  }, []);

  // Toggle favorite status
  const toggleFavorite = useCallback((toolId: ToolId) => {
    if (typeof window === "undefined") {
      return;
    }

    setFavoriteTools((prev) => {
      const isFavorite = prev.includes(toolId);
      const updated = isFavorite
        ? prev.filter((id) => id !== toolId)
        : [...prev, toolId];
      window.localStorage.setItem(FAVORITE_TOOLS_KEY, JSON.stringify(updated));
      return updated;
    });
  }, []);

  // Check if a tool is favorited
  const isFavorite = useCallback(
    (toolId: ToolId): boolean => {
      return favoriteTools.includes(toolId);
    },
    [favoriteTools],
  );

  return {
    recentTools,
    favoriteTools,
    toggleFavorite,
    isFavorite,
  };
}
