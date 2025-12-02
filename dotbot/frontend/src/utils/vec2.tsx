export interface Vec2 {
  x: number;
  y: number;
}

export function vec(x: number, y: number): Vec2 {
  return { x, y };
}

export function add(a: Vec2, b: Vec2): Vec2 {
  return { x: a.x + b.x, y: a.y + b.y };
}

export function sub(a: Vec2, b: Vec2): Vec2 {
  return { x: a.x - b.x, y: a.y - b.y };
}

export function mul(a: Vec2, s: number): Vec2 {
  return { x: a.x * s, y: a.y * s };
}

export function dot(a: Vec2, b: Vec2): number {
  return a.x * b.x + a.y * b.y;
}

export function lengthSq(a: Vec2): number {
  return dot(a, a);
}

export function vec2_length(a: Vec2): number {
  return Math.sqrt(lengthSq(a));
}

export function normalize(a: Vec2): Vec2 {
  const len = vec2_length(a);
  if (len === 0) return { x: 0, y: 0 };
  return { x: a.x / len, y: a.y / len };
}

// Perpendicular (left-hand)
export function perp(a: Vec2): Vec2 {
  return { x: -a.y, y: a.x };
}
