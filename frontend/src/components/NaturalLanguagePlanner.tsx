import {
  type FormEvent,
  useState,
} from "react";

import {
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";

import {
  BrainCircuit,
  CheckCircle2,
  CornerDownRight,
  LoaderCircle,
  Play,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import {
  approveMissionPlan,
  generateMissionPlan,
} from "../api/planner";


function NaturalLanguagePlanner() {
  const queryClient = useQueryClient();

  const [prompt, setPrompt] = useState(
    "Go to Room A, inspect the path, locate "
      + "the red box, capture an image, "
      + "and return home.",
  );


  const plannerMutation = useMutation({
    mutationFn: generateMissionPlan,
  });


  const approvalMutation = useMutation({
    mutationFn: approveMissionPlan,

    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["missions"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["ros-status"],
        }),
      ]);
    },
  });


  function submitPrompt(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const cleanedPrompt = prompt.trim();

    if (cleanedPrompt.length < 5) {
      return;
    }

    approvalMutation.reset();
    plannerMutation.mutate(cleanedPrompt);
  }


  const result = plannerMutation.data;
  const approval = approvalMutation.data;


  return (
    <article className="panel ai-planner-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-eyebrow">
            LOCAL LLM MISSION PLANNER
          </p>

          <h3>Describe the mission naturally</h3>

          <p className="panel-description">
            Qwen2 creates the plan. You approve it
            before ROS2 execution begins.
          </p>
        </div>

        <div className="heading-icon ai-heading-icon">
          <BrainCircuit size={21} />
        </div>
      </div>

      <form
        className="ai-planner-form"
        onSubmit={submitPrompt}
      >
        <textarea
          value={prompt}
          onChange={(event) =>
            setPrompt(event.target.value)
          }
          maxLength={1000}
          placeholder={
            "Describe what the simulated "
            + "robot should do..."
          }
        />

        <div className="planner-form-footer">
          <span>
            {prompt.length}/1000 characters
          </span>

          <button
            className="primary-button planner-button"
            type="submit"
            disabled={
              plannerMutation.isPending ||
              approvalMutation.isPending ||
              prompt.trim().length < 5
            }
          >
            {plannerMutation.isPending ? (
              <>
                <LoaderCircle
                  className="spinner"
                  size={18}
                />
                Generating locally
              </>
            ) : (
              <>
                <Sparkles size={18} />
                Generate AI plan
              </>
            )}
          </button>
        </div>
      </form>

      {plannerMutation.isError && (
        <div className="planner-error">
          The local AI planner could not generate
          the mission. Check Ollama and FastAPI.
        </div>
      )}

      {result && (
        <div className="generated-plan">
          <div className="plan-summary-header">
            <div>
              <span className="generated-label">
                Saved AI plan
              </span>

              <h4>{result.plan.title}</h4>

              <p>{result.plan.summary}</p>
            </div>

            <span
              className={
                `risk-badge risk-`
                + result.plan.risk_level
              }
            >
              {result.plan.risk_level} risk
            </span>
          </div>

          <div className="approval-status">
            <ShieldCheck size={18} />

            <div>
              <strong>
                Human approval required
              </strong>

              <span>
                Plan ID: {result.plan_id}
              </span>
            </div>
          </div>

          <div className="plan-steps">
            {result.plan.steps.map((step) => (
              <div
                className="plan-step"
                key={step.step_number}
              >
                <span className="step-number">
                  {step.step_number}
                </span>

                <CornerDownRight size={17} />

                <div>
                  <strong>
                    {step.action.replaceAll(
                      "_",
                      " ",
                    )}
                  </strong>

                  <span>
                    {step.description}
                  </span>
                </div>

                <code>
                  {step.target ?? "none"}
                </code>
              </div>
            ))}
          </div>

          {result.plan.assumptions.length > 0 && (
            <div className="assumptions-box">
              <strong>Assumptions</strong>

              {result.plan.assumptions.map(
                (assumption, index) => (
                  <span
                    key={`${index}-${assumption}`}
                  >
                    <CheckCircle2 size={13} />
                    {assumption}
                  </span>
                ),
              )}
            </div>
          )}

          <div className="plan-actions">
            <span className="model-label">
              Local model: {result.provider} ·{" "}
              {result.model}
            </span>

            <button
              type="button"
              className="primary-button approve-button"
              disabled={
                approvalMutation.isPending ||
                approvalMutation.isSuccess
              }
              onClick={() =>
                approvalMutation.mutate(
                  result.plan_id
                )
              }
            >
              {approvalMutation.isPending ? (
                <>
                  <LoaderCircle
                    className="spinner"
                    size={18}
                  />
                  Starting mission
                </>
              ) : approvalMutation.isSuccess ? (
                <>
                  <CheckCircle2 size={18} />
                  Mission launched
                </>
              ) : (
                <>
                  <Play size={18} />
                  Approve & Execute
                </>
              )}
            </button>
          </div>

          {approvalMutation.isError && (
            <div className="planner-error">
              The plan could not be approved or
              sent to ROS2.
            </div>
          )}

          {approval && (
            <div className="approval-success">
              <CheckCircle2 size={20} />

              <div>
                <strong>
                  Mission sent to ROS2
                </strong>

                <span>
                  Mission ID:{" "}
                  {approval.mission_id}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  );
}


export default NaturalLanguagePlanner;
