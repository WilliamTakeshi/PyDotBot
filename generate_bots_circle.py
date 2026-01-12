import math

N_BOTS = 10
CENTER_X = 500_000
CENTER_Y = 500_000
RADIUS = 400_000  # spacing radius

def gen_address(i: int) -> str:
    return f"AAAAAAAAAAAAAA{i:02X}"

def clamp_theta(t: float) -> float:
    return max(0.0, min(6.14, t))

def generate_circle_toml() -> str:
    blocks = []

    for i in range(N_BOTS):
        angle = 2 * math.pi * i / N_BOTS

        x = int(CENTER_X + RADIUS * math.cos(angle))
        y = int(CENTER_Y + RADIUS * math.sin(angle))

        # Facing outward
        theta = clamp_theta(angle)

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

    with open("circle_10_bots.toml", "w") as f:
        f.write(toml_str)
