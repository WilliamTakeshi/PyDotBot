import math

N_BOTS = 128
CENTER_X = 500_000
CENTER_Y = 500_000
RADIUS = 300_000  # spacing radius

def gen_address(i: int) -> str:
    return f"AAAAAAAAAAAA{i:04X}"

def normalize_theta(t: float) -> float:
    """Normalize angle to [0, 2π)."""
    t = t % (2 * math.pi)
    return t

def generate_circle_toml() -> str:
    blocks = []

    for i in range(N_BOTS):
        angle = 2 * math.pi * i / N_BOTS

        x = int(CENTER_X + RADIUS * math.cos(angle))
        y = int(CENTER_Y + RADIUS * math.sin(angle))

        # Facing outward
        # theta = normalize_theta(angle)

        # Facing tangencially
        theta = normalize_theta(angle - math.pi / 2)

        block = f"""[[dotbots]]
address = "{gen_address(i)}"
calibrated = true
pos_x = {x}
pos_y = {y}
theta = {theta:.5f}
"""
        blocks.append(block)

    return "\n".join(blocks)

if __name__ == "__main__":
    toml_str = generate_circle_toml()
    # print(toml_str)

    with open(f"circle_{N_BOTS}_bots.toml", "w") as f:
        f.write(toml_str)
