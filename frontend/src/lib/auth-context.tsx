"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import {
  api,
  getStoredToken,
  getStoredWorkspaceId,
  setStoredToken,
  setStoredWorkspaceId,
  User,
  Workspace,
} from "./api";

interface AuthContextType {
  user: User | null;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  loading: boolean;
  setActiveWorkspace: (ws: Workspace) => void;
  refreshWorkspaces: () => Promise<void>;
  logout: () => Promise<void>;
  setUserFromAuth: (user: User, token: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspaceState] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadUserData() {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setWorkspaces([]);
      setActiveWorkspaceState(null);
      setLoading(false);
      return;
    }

    try {
      const [currentUser, userWorkspaces] = await Promise.all([
        api.getMe(),
        api.listWorkspaces(),
      ]);

      setUser(currentUser);
      setWorkspaces(userWorkspaces);

      const savedWsId = getStoredWorkspaceId();
      const matched = userWorkspaces.find((w) => w.id === savedWsId);
      if (matched) {
        setActiveWorkspaceState(matched);
      } else if (userWorkspaces.length > 0) {
        setActiveWorkspaceState(userWorkspaces[0]);
        setStoredWorkspaceId(userWorkspaces[0].id);
      }
    } catch {
      // If token is invalid or expired, clear state
      setUser(null);
      setWorkspaces([]);
      setActiveWorkspaceState(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUserData();
  }, []);

  const setActiveWorkspace = (ws: Workspace) => {
    setActiveWorkspaceState(ws);
    setStoredWorkspaceId(ws.id);
  };

  const refreshWorkspaces = async () => {
    try {
      const list = await api.listWorkspaces();
      setWorkspaces(list);
      if (list.length > 0 && !activeWorkspace) {
        setActiveWorkspace(list[0]);
      }
    } catch {
      // ignore
    }
  };

  const setUserFromAuth = async (authUser: User, token: string) => {
    if (token) {
      setStoredToken(token);
    }
    setUser(authUser);
    const list = await api.listWorkspaces();
    setWorkspaces(list);
    if (list.length > 0) {
      setActiveWorkspace(list[0]);
    }
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
    setWorkspaces([]);
    setActiveWorkspaceState(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        workspaces,
        activeWorkspace,
        loading,
        setActiveWorkspace,
        refreshWorkspaces,
        logout,
        setUserFromAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
