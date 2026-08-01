import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import "./MissionReportsPanel.css";


type MissionReport = {
  mission_id: string;
  plan_id: string | null;
  status: string;
  action: string | null;
  target: string | null;
  progress_percent: number;
  current_step: number | null;
  total_steps: number;
  detection_count: number;
  detected_labels: string[];
  capture_path: string | null;
  report_path: string | null;
  error: string | null;
  event_at: string | null;
  created_at: string | null;
  report_download_url: string;
  evidence_download_url: string | null;
};


type ReportsResponse = {
  items: MissionReport[];
  count: number;
};


const formatDate = (
  value: string | null,
): string => {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
};


export default function MissionReportsPanel() {
  const [reports, setReports] =
    useState<MissionReport[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const baseUrl = useMemo(
    () =>
      `${window.location.protocol}//` +
      `${window.location.hostname}:8004`,
    [],
  );

  const loadReports = useCallback(
    async () => {
      try {
        const response = await fetch(
          `${baseUrl}/api/reports?limit=30`,
        );

        if (!response.ok) {
          throw new Error(
            `Reports API returned ${response.status}`,
          );
        }

        const payload =
          (await response.json()) as ReportsResponse;

        setReports(payload.items);
        setError("");

      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load reports",
        );

      } finally {
        setLoading(false);
      }
    },
    [baseUrl],
  );

  useEffect(() => {
    loadReports();

    const interval = window.setInterval(
      loadReports,
      3000,
    );

    return () => {
      window.clearInterval(interval);
    };
  }, [loadReports]);

  const openReport = (
    report: MissionReport,
  ) => {
    window.open(
      `${baseUrl}${report.report_download_url}`,
      "_blank",
      "noopener,noreferrer",
    );
  };

  const openEvidence = (
    report: MissionReport,
  ) => {
    if (!report.evidence_download_url) {
      return;
    }

    window.open(
      `${baseUrl}${report.evidence_download_url}`,
      "_blank",
      "noopener,noreferrer",
    );
  };

  return (
    <section className="mission-reports-panel">
      <div className="reports-header">
        <div>
          <span className="reports-kicker">
            POSTGRESQL + AUTOMATIC PDF REPORTS
          </span>

          <h2>Mission Reports & Evidence</h2>

          <p>
            Downloadable mission records,
            computer-vision results and inspection
            evidence.
          </p>
        </div>

        <div className="reports-header-actions">
          <span className="reports-count">
            {reports.length} reports
          </span>

          <button
            type="button"
            onClick={loadReports}
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="reports-error">
          {error}
        </div>
      )}

      {loading ? (
        <div className="reports-empty">
          Loading mission reports...
        </div>
      ) : reports.length === 0 ? (
        <div className="reports-empty">
          Complete a new mission to generate
          the first PDF report.
        </div>
      ) : (
        <div className="reports-table-wrapper">
          <table className="reports-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Mission</th>
                <th>Action / Target</th>
                <th>Vision</th>
                <th>Created</th>
                <th>Evidence</th>
              </tr>
            </thead>

            <tbody>
              {reports.map((report) => (
                <tr key={report.mission_id}>
                  <td>
                    <span
                      className={
                        `report-status ` +
                        report.status
                      }
                    >
                      {report.status}
                    </span>
                  </td>

                  <td>
                    <strong className="report-mission-id">
                      {report.mission_id}
                    </strong>

                    <small>
                      {report.total_steps} steps ·{" "}
                      {report.progress_percent}%
                    </small>
                  </td>

                  <td>
                    <strong>
                      {report.action ?? "—"}
                    </strong>

                    <small>
                      {report.target ?? "—"}
                    </small>
                  </td>

                  <td>
                    <strong>
                      {report.detection_count}{" "}
                      detections
                    </strong>

                    <small>
                      {report.detected_labels.length
                        ? report.detected_labels.join(
                            ", ",
                          )
                        : "No labels"}
                    </small>
                  </td>

                  <td>
                    <strong>
                      {formatDate(
                        report.created_at,
                      )}
                    </strong>

                    {report.error && (
                      <small className="report-error-text">
                        {report.error}
                      </small>
                    )}
                  </td>

                  <td>
                    <div className="report-buttons">
                      <button
                        type="button"
                        onClick={() =>
                          openReport(report)
                        }
                      >
                        PDF report
                      </button>

                      <button
                        type="button"
                        disabled={
                          !report.evidence_download_url
                        }
                        onClick={() =>
                          openEvidence(report)
                        }
                      >
                        Image
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
