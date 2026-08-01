import { apiClient } from "./client";

import type {
  MissionPlanApprovalResponse,
  MissionPlanResponse,
} from "../types";


export async function generateMissionPlan(
  prompt: string,
): Promise<MissionPlanResponse> {
  const response =
    await apiClient.post<MissionPlanResponse>(
      "/api/mission-plans",
      {
        prompt,
      },
      {
        timeout: 180000,
      },
    );

  return response.data;
}


export async function approveMissionPlan(
  planId: string,
): Promise<MissionPlanApprovalResponse> {
  const response =
    await apiClient.post<MissionPlanApprovalResponse>(
      `/api/mission-plans/${planId}/approve`,
    );

  return response.data;
}
