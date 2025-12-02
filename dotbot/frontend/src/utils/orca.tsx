// ========== ORCA line / half-plane ==========

import {
  add,
  dot,
  lengthSq,
  mul,
  normalize,
  perp,
  sub,
  vec,
  vec2_length,
  type Vec2,
} from "./vec2.tsx";

/**
 * ORCA line: represents a half-plane constraint
 *  { v | (v - point) · n >= 0 }
 *
 * We store as: point + direction * t (line itself), with normal = perp(direction)
 */
export interface OrcaLine {
  point: Vec2; // a point on the line
  direction: Vec2; // normalized direction of the line
  normal: Vec2; // outward normal of the half-plane (perp(direction)), normalized
}

// ========== Agent ==========

export interface Agent {
  id: string;

  position: Vec2;
  velocity: Vec2;
  radius: number;
  maxSpeed: number;

  preferredVelocity: Vec2;
}

/**
 * Parameters for ORCA solver.
 * timeHorizon: > 0, "how far" into the future to avoid collisions.
 */
export interface OrcaParams {
  timeHorizon: number; // e.g. 3.0
}

/**
 * Compute ORCA lines for agent A w.r.t. a list of neighbors.
 */
export function computeOrcaLinesForAgent(
  agent: Agent,
  neighbors: Agent[],
  params: OrcaParams
): OrcaLine[] {
  const lines: OrcaLine[] = [];

  for (const other of neighbors) {
    if (other.id === agent.id) continue;
    lines.push(computeOrcaLinePair(agent, other, params));
  }

  return lines;
}

/**
 * Compute one ORCA line for collision avoidance of agent A w.r.t. B.
 * This is essentially the 2D ORCA construction for circular agents.
 */
export function computeOrcaLinePair(
  A: Agent,
  B: Agent,
  params: OrcaParams
): OrcaLine {
  const timeHorizon = params.timeHorizon;

  const relPos = sub(B.position, A.position);
  const relVel = sub(A.velocity, B.velocity);
  const distSq = lengthSq(relPos);
  const combinedRadius = A.radius + B.radius;
  const combinedRadiusSq = combinedRadius * combinedRadius;

  const line: OrcaLine = {
    point: { x: 0, y: 0 },
    direction: { x: 0, y: 0 },
    normal: { x: 0, y: 0 },
  };

  // Case 1: No collision yet (dist > combinedRadius)
  if (distSq > combinedRadiusSq) {
    // "Optimal" relative velocity is relPos / timeHorizon
    // This gives a truncated VO with horizon timeHorizon.
    const invTimeHorizon = 1.0 / timeHorizon;
    const w = sub(relVel, mul(relPos, invTimeHorizon)); // shift by VO apex
    const wLenSq = lengthSq(w);

    const dotWRelPos = dot(w, relPos);

    // Check if w is inside the cone or beyond cutoff circle
    // If projected on circle arc:
    if (dotWRelPos < 0 && dotWRelPos * dotWRelPos > combinedRadiusSq * wLenSq) {
      // Project on cutoff circle
      const wLen = Math.sqrt(wLenSq);
      const unitW = mul(w, 1.0 / wLen);

      // Smallest change u to push w to boundary of VO circle
      const u = mul(unitW, combinedRadius * invTimeHorizon - wLen);

      // A takes half of u
      line.point = add(A.velocity, mul(u, 0.5));
      line.normal = unitW; // outward normal
      line.direction = perp(line.normal); // tangent direction
    } else {
      // Project on legs of cone (tangents to disc)
      const dist = Math.sqrt(distSq);
      const relPosUnit = mul(relPos, 1.0 / dist);

      // Compute leg length
      const leg = Math.sqrt(distSq - combinedRadiusSq);

      // Left and right leg directions
      const leftLegDir: Vec2 = {
        x: (relPos.x * leg - relPos.y * combinedRadius) / distSq,
        y: (relPos.x * combinedRadius + relPos.y * leg) / distSq,
      };

      const rightLegDir: Vec2 = {
        x: (relPos.x * leg + relPos.y * combinedRadius) / distSq,
        y: (-relPos.x * combinedRadius + relPos.y * leg) / distSq,
      };

      // Decide which leg is relevant based on relVel
      const side = Math.sign(
        cross(relVel, relPosUnit) // cross product in 2D
      );

      let legDir: Vec2;
      if (side >= 0) {
        // Use left leg
        legDir = leftLegDir;
      } else {
        // Use right leg
        legDir = rightLegDir;
      }

      // Project relVel onto chosen leg
      const proj = dot(relVel, legDir);
      const closestPoint = mul(legDir, proj);

      const u = sub(closestPoint, relVel); // minimal change

      line.point = add(A.velocity, mul(u, 0.5));
      line.direction = legDir;
      line.normal = perp(line.direction);
      line.normal = normalize(line.normal);
    }
  } else {
    // Case 2: Agents are already colliding or too close (dist <= combinedRadius)
    // Push them apart in the direction of relPos
    const dist = Math.sqrt(distSq);
    const relPosUnit = dist > 0 ? mul(relPos, 1.0 / dist) : vec(1, 0); // arbitrary if same pos

    const penetration = combinedRadius - dist;
    const u = mul(relPosUnit, penetration);

    line.point = add(A.velocity, mul(u, 0.5));
    line.normal = relPosUnit; // push away from other
    line.direction = perp(line.normal);
  }

  // Normalize direction (defensive)
  line.direction = normalize(line.direction);
  line.normal = normalize(line.normal);

  return line;
}

/**
 * 2D cross product (z-component).
 */
function cross(a: Vec2, b: Vec2): number {
  return a.x * b.y - a.y * b.x;
}

// ========== Linear program: find v closest to vPref inside all ORCA half-planes ==========

/**
 * Solve:
 *   minimize ||v - vPref||^2
 *   subject to: v in disc(0, maxSpeed) and (v - line.point) · line.normal >= 0 for all lines
 */
export function solveOrcaVelocity(
  vPref: Vec2,
  maxSpeed: number,
  lines: OrcaLine[]
): Vec2 {
  // Start with vPref but clamped to maxSpeed
  let result = vPref;
  const lenPrefSq = lengthSq(vPref);
  if (lenPrefSq > maxSpeed * maxSpeed) {
    result = mul(normalize(vPref), maxSpeed);
  }

  // Incrementally enforce each line constraint
  for (let i = 0; i < lines.length; ++i) {
    const line = lines[i];
    if (isFeasible(line, result)) continue;

    // Project vPref onto this line (ignoring others), then fix with earlier lines
    result = projectOnLineAndFix(line, vPref, maxSpeed, lines, i);
  }

  return result;
}

function isFeasible(line: OrcaLine, v: Vec2): boolean {
  const rel = sub(v, line.point);
  return dot(rel, line.normal) >= 0;
}

/**
 * Based on de Berg et al. incremental LP:
 *   Given that previous lines [0..lineNo-1] already enforced,
 *   enforce the new line "line" and keep v as close as possible to vPref.
 */
function projectOnLineAndFix(
  line: OrcaLine,
  vPref: Vec2,
  maxSpeed: number,
  lines: OrcaLine[],
  lineNo: number
): Vec2 {
  // Project vPref onto line
  const t = projectScalar(vPref, line);
  let v = add(line.point, mul(line.direction, t));

  // Clamp to circle
  const lenSqV = lengthSq(v);
  if (lenSqV > maxSpeed * maxSpeed) {
    v = mul(normalize(v), maxSpeed);
  }

  // Now fix with all previous lines
  for (let i = 0; i < lineNo; ++i) {
    const prev = lines[i];
    if (isFeasible(prev, v)) continue;

    // Intersect line i with current line
    v = intersectLines(prev, line, maxSpeed, vPref);
  }

  return v;
}

/**
 * Project vPref onto infinite line defined by ORCA line.
 * Line: v = point + direction * t
 */
function projectScalar(vPref: Vec2, line: OrcaLine): number {
  const rel = sub(vPref, line.point);
  return dot(rel, line.direction);
}

/**
 * Intersect two infinite lines and clamp to speed circle,
 * picking solution closest to vPref.
 */
function intersectLines(
  a: OrcaLine,
  b: OrcaLine,
  maxSpeed: number,
  vPref: Vec2
): Vec2 {
  // Solve: a.point + a.dir * s  and  b.point + b.dir * t
  // For intersection in least-squares sense we can solve via 2x2 system
  const p = a.point;
  const r = a.direction;
  const q = b.point;
  const s = b.direction;

  const rxs = cross(r, s);
  const q_p = sub(q, p);

  let v: Vec2;

  if (Math.abs(rxs) < 1e-6) {
    // Parallel lines: pick projection of vPref onto line a
    const t = projectScalar(vPref, a);
    v = add(p, mul(r, t));
  } else {
    const t = cross(q_p, s) / rxs;
    v = add(p, mul(r, t));
  }

  // Clamp to circle
  const lenSqV = lengthSq(v);
  if (lenSqV > maxSpeed * maxSpeed) {
    v = mul(normalize(v), maxSpeed);
  }

  return v;
}

// ========== High-level helper for one agent step ==========

/**
 * Compute new collision-avoiding velocity for a single agent.
 *
 * neighbors: other agents
 * params: ORCA params
 *
 * Returns a velocity vector (vx, vy) you then pass to your
 * (vx, vy) → (left, right) mapper.
 */
export function computeOrcaVelocityForAgent(
  agent: Agent,
  neighbors: Agent[],
  params: OrcaParams
): Vec2 {
  const lines = computeOrcaLinesForAgent(agent, neighbors, params);
  const vNew = solveOrcaVelocity(
    agent.preferredVelocity,
    agent.maxSpeed,
    lines
  );
  return vNew;
}

export function computeOrcaVelocityTowardGoal(
  agent: Agent,
  neighbors: Agent[],
  goal: Vec2,
  params: OrcaParams
): Vec2 {
  // 1. Compute preferred velocity: direction to goal

  const diff = sub(goal, agent.position);
  const dist = vec2_length(diff);

  // If already at the goal, no preferred movement.
  let preferred: Vec2;
  if (dist < 1e-6) {
    preferred = vec(0, 0);
  } else {
    const direction = normalize(diff);
    preferred = mul(direction, agent.maxSpeed);
  }

  // 2. Build ORCA constraints
  const lines = computeOrcaLinesForAgent(agent, neighbors, params);

  // 3. Compute collision-free velocity closest to preferred
  const vNew = solveOrcaVelocity(preferred, agent.maxSpeed, lines);

  return vNew;
}
