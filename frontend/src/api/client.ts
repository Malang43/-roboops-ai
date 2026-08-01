import axios from "axios";

import type {
  HealthResponse,
  MissionListResponse,
  MissionRecord,
  MissionRequest,
  MissionResponse,
  RosStatusResponse,
} from "../types";


const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000";


export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});


export async function getHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>(
    "/api/health",
  );

  return response.data;
}


export async function getRosStatus(): Promise<RosStatusResponse> {
  const response = await apiClient.get<RosStatusResponse>(
    "/api/ros/status",
  );

  return response.data;
}


export async function createMission(
  mission: MissionRequest,
): Promise<MissionResponse> {
  const response = await apiClient.post<MissionResponse>(
    "/api/missions",
    mission,
  );

  return response.data;
}


export async function getMissions(
  limit = 100,
): Promise<MissionListResponse> {
  const response = await apiClient.get<MissionListResponse>(
    "/api/missions",
    {
      params: {
        limit,
      },
    },
  );

  return response.data;
}


export async function getMission(
  missionId: string,
): Promise<MissionRecord> {
  const response = await apiClient.get<MissionRecord>(
    `/api/missions/${missionId}`,
  );

  return response.data;
}
