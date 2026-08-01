export type MissionAction =
  | "navigate"
  | "detect_object"
  | "capture_image"
  | "inspect_path"
  | "return_home";


export type MissionStatus =
  | "queued"
  | "sent"
  | "received"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | string;


export interface MissionRequest {
  action: MissionAction;
  target: string | null;
}


export interface MissionRecord {
  mission_id: string;
  action: string;
  target: string | null;
  status: MissionStatus;
  worker: string | null;
  error: string | null;
  last_event: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}


export interface MissionResponse {
  accepted: boolean;
  mission: MissionRecord;
}


export interface MissionListResponse {
  total: number;
  items: MissionRecord[];
}


export interface HealthResponse {
  status: string;
  service: string;
  timestamp: string;
}


export interface MissionStatusEvent {
  mission_id?: string;
  plan_id?: string;
  action?: string;
  target?: string | null;
  description?: string | null;
  status?: string;
  worker?: string;
  event_at?: string;
  current_step?: number | null;
  total_steps?: number;
  step_status?: string | null;
  progress_percent?: number;
  error?: string;
}


export interface RosStatusResponse {
  connected: boolean;
  node_name: string | null;
  latest_status: MissionStatusEvent | null;
}


export interface MissionPlanStep {
  step_number: number;
  action: MissionAction;
  target: string | null;
  description: string;
}


export interface MissionPlan {
  title: string;
  summary: string;
  risk_level: "low" | "medium" | "high";
  requires_approval: boolean;
  assumptions: string[];
  steps: MissionPlanStep[];
}


export interface MissionPlanResponse {
  plan_id: string;
  status: string;
  prompt: string;
  provider: string;
  model: string;
  plan: MissionPlan;
}


export interface MissionPlanApprovalResponse {
  approved: boolean;
  plan_id: string;
  mission_id: string;
  plan_status: string;
  mission_status: string;
  message: string;
}
