import { useMemo, useState } from "react";

import {
  Bot,
  ChevronRight,
  Clock3,
  ListFilter,
} from "lucide-react";

import type {
  MissionRecord,
} from "../types";


type MissionFilter =
  | "all"
  | "active"
  | "completed"
  | "failed";


interface MissionHistoryProps {
  missions: MissionRecord[];
  total: number;
  isLoading: boolean;
  selectedMissionId: string | null;
  onSelectMission: (missionId: string) => void;
}


const activeStatuses = new Set([
  "queued",
  "sent",
  "received",
  "running",
]);


function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}


function MissionHistory({
  missions,
  total,
  isLoading,
  selectedMissionId,
  onSelectMission,
}: MissionHistoryProps) {
  const [filter, setFilter] =
    useState<MissionFilter>("all");


  const filteredMissions = useMemo(() => {
    if (filter === "active") {
      return missions.filter((mission) =>
        activeStatuses.has(mission.status),
      );
    }

    if (filter === "completed") {
      return missions.filter(
        (mission) =>
          mission.status === "completed",
      );
    }

    if (filter === "failed") {
      return missions.filter(
        (mission) =>
          mission.status === "failed" ||
          mission.status === "cancelled",
      );
    }

    return missions;
  }, [filter, missions]);


  return (
    <article className="panel history-panel">
      <div className="panel-heading history-heading">
        <div>
          <p className="panel-eyebrow">
            MISSION DATABASE
          </p>

          <h3>Mission history</h3>

          <p className="panel-description">
            {total} missions stored in PostgreSQL
          </p>
        </div>

        <div className="filter-group">
          <ListFilter size={16} />

          {(
            [
              "all",
              "active",
              "completed",
              "failed",
            ] as MissionFilter[]
          ).map((item) => (
            <button
              key={item}
              type="button"
              className={
                filter === item
                  ? "filter-button filter-button-active"
                  : "filter-button"
              }
              onClick={() => setFilter(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="history-empty">
          Loading missions...
        </div>
      ) : filteredMissions.length === 0 ? (
        <div className="history-empty">
          <Bot size={35} />

          <strong>No missions found</strong>

          <span>
            Launch a mission or select another filter.
          </span>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="mission-table">
            <thead>
              <tr>
                <th>Mission</th>
                <th>Action</th>
                <th>Target</th>
                <th>Status</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>

            <tbody>
              {filteredMissions.map((mission) => (
                <tr
                  key={mission.mission_id}
                  className={
                    selectedMissionId ===
                    mission.mission_id
                      ? "selected-row"
                      : ""
                  }
                  onClick={() =>
                    onSelectMission(
                      mission.mission_id,
                    )
                  }
                >
                  <td>
                    <div className="mission-reference">
                      <span className="mission-reference-icon">
                        <Bot size={16} />
                      </span>

                      <code>
                        {mission.mission_id.slice(
                          0,
                          8,
                        )}
                      </code>
                    </div>
                  </td>

                  <td className="action-cell">
                    {mission.action.replaceAll(
                      "_",
                      " ",
                    )}
                  </td>

                  <td>
                    {mission.target ?? "—"}
                  </td>

                  <td>
                    <span
                      className={`status-badge status-${mission.status}`}
                    >
                      {mission.status}
                    </span>
                  </td>

                  <td>
                    <span className="date-cell">
                      <Clock3 size={14} />

                      {formatDate(
                        mission.created_at,
                      )}
                    </span>
                  </td>

                  <td>
                    <ChevronRight
                      className="row-arrow"
                      size={17}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}


export default MissionHistory;
