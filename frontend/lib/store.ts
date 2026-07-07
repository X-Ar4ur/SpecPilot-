"use client";

import { create } from "zustand";

type AppState = {
  sidebarCollapsed: boolean;
  settingsOpen: boolean;
  toggleSidebar: () => void;
  openSettings: () => void;
  closeSettings: () => void;
  setSettingsOpen: (open: boolean) => void;
};

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  settingsOpen: false,
  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  openSettings: () => set({ settingsOpen: true }),
  closeSettings: () => set({ settingsOpen: false }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),
}));
