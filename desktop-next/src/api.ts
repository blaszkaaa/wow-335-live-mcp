import { invoke } from "@tauri-apps/api/core";
import type { Dashboard } from "./types";
type Action = "dashboard" | "refresh" | "launch" | "demo" | "get_settings" | "set_settings";
export async function backend(action: Action, payload?: Record<string,unknown>): Promise<any> {
  return invoke("backend_api", {action,payload:payload ?? null});
}
export async function getDashboard(): Promise<Dashboard> {
  return backend("dashboard") as Promise<Dashboard>;
}
export async function chooseGameDirectory(): Promise<string|null> {
  const {open} = await import("@tauri-apps/plugin-dialog");
  const value = await open({directory:true,multiple:false,title:"Wybierz folder World of Warcraft 3.3.5a"});
  return typeof value==="string" ? value : null;
}
