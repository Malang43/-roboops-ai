import {
  Bot,
  CalendarClock,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Code2,
  MapPin,
  X,
} from "lucide-react";

import type {
  MissionRecord,
} from "../types";


interface MissionDetailsProps {
  mission: MissionRecord | null;
  isLoading: boolean;
  onClose: () => void;
}


function formatDate(
  value: string | null,
): string {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}


function MissionDetails({
  mission,
  isLoading,
  onClose,
}: MissionDetailsProps) {
  if (!mission && !isLoading) {
    return null;
  }

  return (
    <div
      className="details-backdrop"
      onClick={onClose}
    >
      <aside
        className="details-panel"
        onClick={(event) =>
          event.stopPropagation()
        }
      >
        <div className="details-header">
          <div>
            <p className="panel-eyebrow">
              MISSION DETAILS
            </p>

            <h3>
              {isLoading
                ? "Loading mission"
                : "Mission information"}
            </h3>
          </div>

          <button
            type="button"
            className="close-button"
            onClick={onClose}
            aria-label="Close mission details"
          >
            <X size={19} />
          </button>
        </div>

        {isLoading || !mission ? (
          <div className="details-loading">
            Loading...
          </div>
        ) : (
          <div className="details-content">
            <div className="details-status-card">
              <div>
                {mission.status === "completed" ? (
                  <CheckCircle2 size={26} />
                ) : mission.status === "failed" ? (
                  <CircleAlert size={26} />
                ) : (
                  <Bot size={26} />
                )}
              </div>

              <div>
                <span>Current status</span>

                <strong>
                  {mission.status}
                </strong>
              </div>
            </div>

            <div className="details-section">
              <h4>Mission</h4>

              <div className="details-row">
                <span>
                  <Code2 size={16} />
                  Mission ID
                </span>

                <code>{mission.mission_id}</code>
              </div>

              <div className="details-row">
                <span>
                  <Bot size={16} />
                  Action
                </span>

                <strong>
                  {mission.action.replaceAll(
                    "_",
                    " ",
                  )}
                </strong>
              </div>

              <div className="details-row">
                <span>
                  <MapPin size={16} />
                  Target
                </span>

                <strong>
                  {mission.target ?? "—"}
                </strong>
              </div>

              <div className="details-row">
                <span>
                  <Bot size={16} />
                  Worker
                </span>

                <strong>
                  {mission.worker ?? "Waiting"}
                </strong>
              </div>
            </div>

            <div className="details-section">
              <h4>Timeline</h4>

              <div className="details-row">
                <span>
                  <CalendarClock size={16} />
                  Created
                </span>

                <strong>
                  {formatDate(
                    mission.created_at,
                  )}
                </strong>
              </div>

              <div className="details-row">
                <span>
                  <Clock3 size={16} />
                  Started
                </span>

                <strong>
                  {formatDate(
                    mission.started_at,
                  )}
                </strong>
              </div>

              <div className="details-row">
                <span>
                  <CheckCircle2 size={16} />
                  Completed
                </span>

                <strong>
                  {formatDate(
                    mission.completed_at,
                  )}
                </strong>
              </div>
            </div>

            {mission.error && (
              <div className="mission-error-box">
                <CircleAlert size={18} />

                <div>
                  <strong>Mission error</strong>
                  <span>{mission.error}</span>
                </div>
              </div>
            )}

            <div className="details-section">
              <h4>Latest ROS2 event</h4>

              <pre className="event-json">
                {JSON.stringify(
                  mission.last_event,
                  null,
                  2,
                )}
              </pre>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}


export default MissionDetails;
