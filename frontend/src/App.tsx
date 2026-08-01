import MissionReportsPanel from "./components/MissionReportsPanel";
import LiveVisionPanel from "./components/LiveVisionPanel";
import LiveRobotTelemetry from "./components/LiveRobotTelemetry";
import {
  type FormEvent,
  useState,
} from "react";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  Activity,
  Bot,
  CheckCircle2,
  CircleAlert,
  Cpu,
  Database,
  LoaderCircle,
  MapPin,
  Play,
  Radio,
  Route,
  Server,
  Sparkles,
  Target,
  Wifi,
  WifiOff,
} from "lucide-react";

import {
  createMission,
  getHealth,
  getMission,
  getMissions,
  getRosStatus,
} from "./api/client";

import MissionDetails from "./components/MissionDetails";
import MissionHistory from "./components/MissionHistory";
import NaturalLanguagePlanner from "./components/NaturalLanguagePlanner";

import type {
  MissionAction,
  MissionResponse,
} from "./types";


const actions: Array<{
  value: MissionAction;
  label: string;
}> = [
  {
    value: "navigate",
    label: "Navigate",
  },
  {
    value: "detect_object",
    label: "Detect object",
  },
  {
    value: "capture_image",
    label: "Capture image",
  },
  {
    value: "inspect_path",
    label: "Inspect path",
  },
  {
    value: "return_home",
    label: "Return home",
  },
];


function App() {
  const queryClient = useQueryClient();

  const [action, setAction] =
    useState<MissionAction>("navigate");

  const [target, setTarget] =
    useState("room_a");

  const [submittedMission, setSubmittedMission] =
    useState<MissionResponse | null>(null);

  const [
    selectedMissionId,
    setSelectedMissionId,
  ] = useState<string | null>(null);


  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 5000,
  });


  const rosQuery = useQuery({
    queryKey: ["ros-status"],
    queryFn: getRosStatus,
    refetchInterval: 2000,
  });


  const missionsQuery = useQuery({
    queryKey: ["missions"],
    queryFn: () => getMissions(100),
    refetchInterval: 2000,
  });


  const selectedMissionQuery = useQuery({
    queryKey: [
      "mission",
      selectedMissionId,
    ],
    queryFn: () =>
      getMission(selectedMissionId as string),
    enabled: selectedMissionId !== null,
    refetchInterval: selectedMissionId
      ? 2000
      : false,
  });


  const missionMutation = useMutation({
    mutationFn: createMission,

    onSuccess: async (response) => {
      setSubmittedMission(response);
      setSelectedMissionId(
        response.mission.mission_id,
      );

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["ros-status"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["missions"],
        }),
      ]);
    },
  });


  function submitMission(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    missionMutation.mutate({
      action,
      target: target.trim() || null,
    });
  }


  const apiOnline =
    healthQuery.isSuccess &&
    healthQuery.data.status === "ok";

  const rosConnected =
    rosQuery.data?.connected ?? false;

  const latestStatus =
    rosQuery.data?.latest_status ?? null;

  const missions =
    missionsQuery.data?.items ?? [];

  const missionTotal =
    missionsQuery.data?.total ?? 0;


  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Bot size={25} />
          </div>

          <div>
            <h1>RoboOps AI</h1>
            <p>Mission Control</p>
          </div>
        </div>

        <nav className="navigation">
          <button className="nav-item nav-item-active">
            <Activity size={19} />
            Dashboard
          </button>

          <button className="nav-item" disabled>
            <Route size={19} />
            Missions
          </button>

          <button className="nav-item" disabled>
            <Cpu size={19} />
            Robot systems
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="server-label">
            <Server size={16} />
            Titans Server
          </div>

          <span className="server-status">
            <span className="status-dot" />
            Connected
          </span>
        </div>
      </aside>

      <main className="main-content">
        <header className="page-header">
          <div>
            <p className="eyebrow">
              AI ROBOT OPERATIONS PLATFORM
            </p>

            <h2>Mission Control Dashboard</h2>

            <p className="header-description">
              Launch ROS2 missions, monitor their
              lifecycle, and inspect mission records
              stored in PostgreSQL.
            </p>
          </div>

          <div className="header-badge">
            <Sparkles size={17} />
            Software simulation
          </div>
        </header>

        <section className="status-grid status-grid-four">
          <article className="status-card">
            <div className="status-icon api-icon">
              <Server size={22} />
            </div>

            <div>
              <span>FastAPI Backend</span>

              <strong>
                {healthQuery.isLoading
                  ? "Checking"
                  : apiOnline
                    ? "Online"
                    : "Offline"}
              </strong>
            </div>

            {apiOnline ? (
              <CheckCircle2
                className="success-icon"
                size={21}
              />
            ) : (
              <CircleAlert
                className="error-icon"
                size={21}
              />
            )}
          </article>

          <article className="status-card">
            <div className="status-icon ros-icon">
              <Radio size={22} />
            </div>

            <div>
              <span>ROS2 Bridge</span>

              <strong>
                {rosConnected
                  ? "Connected"
                  : "Disconnected"}
              </strong>
            </div>

            {rosConnected ? (
              <Wifi
                className="success-icon"
                size={21}
              />
            ) : (
              <WifiOff
                className="error-icon"
                size={21}
              />
            )}
          </article>

          <article className="status-card">
            <div className="status-icon worker-icon">
              <Bot size={22} />
            </div>

            <div>
              <span>Mission Worker</span>

              <strong>
                {latestStatus?.worker
                  ? "Responding"
                  : "Waiting"}
              </strong>
            </div>

            <span className="pulse-indicator" />
          </article>

          <article className="status-card">
            <div className="status-icon database-icon">
              <Database size={22} />
            </div>

            <div>
              <span>Stored Missions</span>

              <strong>{missionTotal}</strong>
            </div>

            <CheckCircle2
              className="success-icon"
              size={21}
            />
          </article>
        </section>

        <MissionReportsPanel />

      <LiveVisionPanel />

      <LiveRobotTelemetry />

        <NaturalLanguagePlanner />

        <section className="dashboard-grid">
          <article className="panel mission-panel">
            <div className="panel-heading">
              <div>
                <p className="panel-eyebrow">
                  NEW MISSION
                </p>

                <h3>Create mission</h3>
              </div>

              <div className="heading-icon">
                <Target size={20} />
              </div>
            </div>

            <form
              className="mission-form"
              onSubmit={submitMission}
            >
              <label>
                Mission action

                <select
                  value={action}
                  onChange={(event) =>
                    setAction(
                      event.target
                        .value as MissionAction,
                    )
                  }
                >
                  {actions.map((item) => (
                    <option
                      key={item.value}
                      value={item.value}
                    >
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Target or location

                <div className="input-wrapper">
                  <MapPin size={18} />

                  <input
                    value={target}
                    onChange={(event) =>
                      setTarget(
                        event.target.value,
                      )
                    }
                    placeholder="For example: room_a"
                    maxLength={100}
                  />
                </div>
              </label>

              <button
                className="primary-button"
                type="submit"
                disabled={
                  missionMutation.isPending ||
                  !rosConnected
                }
              >
                {missionMutation.isPending ? (
                  <>
                    <LoaderCircle
                      className="spinner"
                      size={18}
                    />
                    Sending mission
                  </>
                ) : (
                  <>
                    <Play size={18} />
                    Launch mission
                  </>
                )}
              </button>

              {!rosConnected && (
                <p className="form-warning">
                  Start the ROS2 bridge before
                  launching a mission.
                </p>
              )}

              {missionMutation.isError && (
                <p className="form-error">
                  Mission could not be sent.
                </p>
              )}

              {submittedMission && (
                <div className="mission-accepted">
                  <CheckCircle2 size={20} />

                  <div>
                    <strong>
                      Mission accepted
                    </strong>

                    <span>
                      ID:{" "}
                      {
                        submittedMission
                          .mission.mission_id
                      }
                    </span>
                  </div>
                </div>
              )}
            </form>
          </article>

          <article className="panel status-panel">
            <div className="panel-heading">
              <div>
                <p className="panel-eyebrow">
                  LIVE ROS2 RESPONSE
                </p>

                <h3>Latest mission status</h3>
              </div>

              <div className="live-label">
                <span />
                Live
              </div>
            </div>

            {latestStatus ? (
              <div className="status-details">
                <div className="detail-row">
                  <span>Status</span>

                  <strong className="status-value">
                    {latestStatus.status ??
                      "Unknown"}
                  </strong>
                </div>

                <div className="detail-row">
                  <span>Action</span>

                  <strong>
                    {latestStatus.action ?? "—"}
                  </strong>
                </div>

                <div className="detail-row">
                  <span>Target</span>

                  <strong>
                    {latestStatus.target ?? "—"}
                  </strong>
                </div>

                <div className="detail-row">
                  <span>Worker</span>

                  <strong>
                    {latestStatus.worker ?? "—"}
                  </strong>
                </div>

                <div className="mission-id-box">
                  <span>Mission ID</span>

                  <code>
                    {latestStatus.mission_id ??
                      "—"}
                  </code>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <Bot size={42} />

                <h4>No mission response yet</h4>

                <p>
                  Launch a mission to see the
                  ROS2 response.
                </p>
              </div>
            )}
          </article>
        </section>

        <MissionHistory
          missions={missions}
          total={missionTotal}
          isLoading={missionsQuery.isLoading}
          selectedMissionId={
            selectedMissionId
          }
          onSelectMission={
            setSelectedMissionId
          }
        />

        <footer className="dashboard-footer">
          <span>
            API polling:
            <strong> Active</strong>
          </span>

          <span>
            ROS distribution:
            <strong> Humble</strong>
          </span>

          <span>
            Database:
            <strong> PostgreSQL</strong>
          </span>
        </footer>
      </main>

      <MissionDetails
        mission={
          selectedMissionQuery.data ?? null
        }
        isLoading={
          selectedMissionQuery.isLoading
        }
        onClose={() =>
          setSelectedMissionId(null)
        }
      />
    </div>
  );
}


export default App;
