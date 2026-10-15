export interface QuestObjective { text?: string; done?: boolean }
export interface Quest { title?: string; level?: number; ready_to_turn_in?: boolean; complete?: boolean | number; objectives?: QuestObjective[] }
export interface Item { id?: number; name?: string; count?: number }
export interface Character { name?: string; level?: number; realm?: string; class?: string; race?: string; xp?: number; xp_max?: number; health?: number; health_max?: number; power?: number; power_max?: number; money_copper?: number; dead?: boolean }
export interface GameData { captured_at?: number; character?: Character; location?: {zone?: string;subzone?: string}; quests?: Quest[]; bags?: Item[]; equipment?: Item[]; target?: {name?:string;level?:number;health?:number;health_max?:number} }
export interface Dashboard {
  available: boolean; source?: string; source_label?: string; demo?: boolean;
  data?: GameData | null;
  read_in_progress?: boolean; error?: string | null; last_visual_read?: number;
  game?: {installed:boolean;running:boolean;directory:string;addon_installed?:boolean};
  launch?: {status:"idle"|"installing"|"starting"|"started"|"already_running"|"error";busy:boolean;message:string;backup?:string|null};
  launch_mode?: "addon" | "native";
  mcp_client?: {recent:boolean;last_seen_seconds?:number|null;requests?:number;note?:string};
  native_setup?: {ready:boolean;reason:string;bundled?:boolean};
  transport?: {available?:boolean;enabled?:boolean;accepted_frames?:number;rejected_frames?:number;sequence?:number;age_seconds?:number|null;pipe?:string;error?:string|null;session?:string|null}
}
export type Page = "overview"|"character"|"quests"|"inventory"|"diagnostics"|"settings";
