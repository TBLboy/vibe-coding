---
name: b-jetson-robot-policy-deployment
description: Plan, implement, audit, or explain safe edge deployment of robot policy models on NVIDIA Jetson Orin, including PyTorch, ONNX, TensorRT, sensor/action adapters, controller integration, and staged validation. Use only when the user explicitly requests Jetson robot-policy deployment work or a related expert review.
license: MIT
compatibility: codex
metadata:
  type: robotics-edge-deployment-skill-pack
  classification: b-domain-specialized-operation
  output: deployment-dossier-and-verification-evidence
  routing: explicit-only
---

# Jetson Robot Policy Deployment

## Scope And Classification

This is a **B-level specialized domain Skill**, not a lifecycle framework. It owns the engineering chain that makes a learned robot policy usable on a Jetson Orin while preserving the existing controller and independent hardware safety boundary.

Use it for ACT, behavior-cloning, diffusion, vision-language-action, and vision/force/tactile policies. Do not use it to design motor firmware, replace a certified safety system, or claim real-robot validation from simulation, offline replay, or a design document.

The default routing is **explicit-only**: deployment work can build engines, change device environments, or potentially lead to physical robot motion. Load this Skill only on an explicit request such as “deploy a policy to Orin”, “optimize robot inference with TensorRT”, or “review the Jetson control chain”.

## Core Boundary

Maintain this non-negotiable execution path:

```text
sensor observations -> Observation Adapter -> policy -> candidate action
-> Action Adapter -> safety supervisor -> existing robot controller
-> robot SDK / hardware controller
```

- The policy proposes a candidate target; it never directly owns motors or high-frequency servo control.
- The existing controller owns inverse kinematics, trajectory generation, interpolation, and low-level execution.
- Independent hardware protection owns emergency stop, limits, overload protection, and fault containment.
- Force or tactile signals may inform policy decisions, but an independent safety path must be able to limit or stop motion without waiting for model inference.

## First Pass

1. Establish whether the request is a design/review, offline implementation, target-device inference task, Shadow Mode task, or request for real-robot execution. State the current evidence level precisely.
2. Read the active project records, model release artifacts, controller interface, robot configuration, and existing tests before deciding any schema or control behavior.
3. Create or update the lifecycle task, engineering specification, decision record, and work trace when the work is non-trivial. Link them to testable behavior and verification evidence.
4. Ask only the highest-impact unresolved question. Before physical execution, the usual blocker is: what action semantics and controller contract are authoritative (joint/cartesian, absolute/delta, units, order, rate, and safety ownership)?
5. Use current official NVIDIA, framework, or SDK documentation when an implementation depends on a version-specific API, compatibility matrix, or CLI. Do not rely on remembered version combinations.

## Deployment Contract

Require a versioned policy release rather than a weight file alone. At minimum, establish these artifacts or explicitly record what is missing:

```text
model weights and model configuration
observation schema and action schema
normalization statistics
camera and force/tactile configuration
model metadata, checksums, and provenance
fixed test vectors with expected outputs
```

The observation contract must define modality availability/order, color format, image transforms, normalization, state ordering, coordinate frames, history, timestamps, synchronization tolerance, and validity handling.

The action contract must define action type, absolute versus delta semantics, units, dimensions/order, frames, quaternion convention where applicable, action horizon, policy rate, and controller input rate. Treat an unknown action order, frame, unit, or normalization artifact as a blocking integration defect, not a detail to infer.

## Environment And Release Control

Record the target hardware, memory/storage, power mode, thermal configuration, JetPack/L4T/OS/kernel, CUDA, cuDNN, TensorRT, inference runtime, application dependencies, robot SDK, model and schema versions, and engine build settings.

- Resolve compatibility from the JetPack baseline outward. Do not arbitrarily upgrade CUDA, TensorRT, or cuDNN independently on a deployed device.
- Use Docker to reproduce application code and user-space dependencies where helpful; do not misrepresent it as reproducing the host kernel, drivers, device nodes, power configuration, camera drivers, or kernel SDK modules.
- Preserve a portable source artifact such as PyTorch and/or ONNX plus build metadata. Treat a TensorRT engine as a target-environment deployment artifact; rebuild it when relevant GPU architecture, runtime, precision, input profile, or builder settings change.
- Implement an environment self-check that covers GPU availability, runtime versions, device health, camera/robot reachability, model checksum, and test-vector execution before allowing a controllable state.

## Optimization Path

Establish a correct baseline before optimizing:

```text
target-device PyTorch baseline -> numerical comparison -> latency baseline
-> FP16 baseline -> ONNX/TensorRT conversion -> TensorRT FP16 validation
-> optional INT8 calibration and task-level revalidation
```

- Fixed shapes for batch, image size, observation horizon, action horizon, and action dimensions are preferred when the policy contract permits them.
- Measure preprocessing, synchronization, inference, postprocessing, queueing, controller handoff, end-to-end P50/P95/P99, memory, power, temperature, throttling, and long-run stability. FPS alone is insufficient.
- For stochastic or generative policies, fix seed, initial noise, sampler, denoising steps, and inference mode for numerical comparison.
- Split exported modules only for a demonstrated export limitation or measurable gain. Common boundaries are visual/state encoders, conditional denoiser, scheduler, and action postprocessing. Cache features only when their observation validity permits reuse.
- FP16 is the ordinary first precision optimization. Attempt INT8 only with representative calibration data and a new numerical, safety, and closed-loop success-rate assessment.

## Adapter And Execution Design

The `Observation Adapter` must reproduce training-time preprocessing exactly and report invalid, missing, stale, or misaligned data. It must not silently substitute arbitrary sensor values.

The `Action Adapter` must perform inverse normalization, ordering/frame/unit conversion, absolute/delta conversion, action-chunk handling, interpolation, and smoothing. Its output remains a candidate until the safety supervisor approves it.

Use a rolling horizon for chunked/generative actions: predict a horizon, execute a small verified prefix, reacquire fresh observation, then replan. Define explicit behavior for inference timeout, stale observations, action expiry, action-queue exhaustion, discontinuities, NaN/Inf, and controller unavailability. Never let inference block the lower-level control or safety loop.

## Safety Gate

Do not command physical motion, arm a robot, relax a limit, or change production safety behavior without the user's explicit authorization and a known-safe operating boundary. Before any real motion, require all applicable gates:

1. Valid model-release checksum, schema, normalization statistics, and robot configuration.
2. Passing deterministic test vectors and host-to-device numerical comparison within an agreed tolerance.
3. Healthy sensors, synchronization, controller connection, independent emergency-stop path, and enforceable limits.
4. Defined stop/fault transitions for stale input, model timeout/failure, invalid output, action jump, queue exhaustion, and controller fault.
5. Human authorization, supervised operating procedure, low initial speed/torque, clear workspace, and an operator able to stop the system.

Use a state machine with an explicit non-actuating state such as:

```text
INITIALIZING -> WAITING_FOR_SENSORS -> MODEL_READY -> SHADOW_MODE
-> ARMED -> RUNNING -> FAULT / STOPPED
```

Entering `FAULT` stops outbound policy commands and preserves diagnostic evidence. Physical emergency stop remains independent from the Jetson process.

## Evidence Ladder

Advance only with evidence, never by assertion:

1. Host offline replay: output range, shape, smoothness, and recorded data behavior.
2. Orin offline replay: same episodes, numerical comparison, and latency profiling.
3. Shadow Mode: live sensors and recorded candidate actions, with no robot actuation.
4. Low-speed, low-torque, supervised, empty-workspace execution using short verified prefixes.
5. Closed-loop task validation with controlled variation, contact cases where relevant, and long-run monitoring.

Record each stage as passed, failed, blocked, or implemented-unverified, along with commands, device configuration, artifacts, metrics, tolerances, and limitations. A successful engine build does not demonstrate behavioral equivalence or real-robot safety.

## Required Output

Produce a concise deployment dossier appropriate to the request:

- **System boundary:** the sensor-to-controller chain and ownership of safety/control responsibilities.
- **Contract matrix:** observation/action fields, source of truth, conversions, validation, and blocking ambiguities.
- **Release manifest:** model, schemas, normalizers, device/runtime versions, engine provenance, and checksums.
- **Performance report:** end-to-end latency percentiles, resources, thermal/power state, and decision against the required control cadence.
- **Safety and state behavior:** fault triggers, safe fallback, Shadow Mode, arming controls, and physical-operation prerequisites.
- **Verification record:** evidence ladder status, exact results, known gaps, and next safe step.

For interview preparation, distinguish completed real-robot deployment from design, simulation, offline replay, or Shadow Mode work. Describe only evidence that exists.

## Evaluation Example

Given a diffusion policy that outputs 16 normalized joint-delta actions at 20 Hz while the existing controller accepts absolute joint targets at 100 Hz, the Skill must require: the training normalizer; authoritative joint order and radians convention; conversion from current joint state plus delta; bounded interpolation to 100 Hz; a rolling-prefix policy; inference/queue timeout behavior; host/Orin fixed-noise comparison; and Shadow Mode before any supervised low-speed robot command. It must not recommend sending the 16 raw outputs directly to the controller.
