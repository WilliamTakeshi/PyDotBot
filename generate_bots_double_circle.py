import math

N_BOTS = 128
CENTER_X = 500_000
CENTER_Y = 500_000
RADII = [300_000, 400_000]  # two circles

assert N_BOTS % len(RADII) == 0
BOTS_PER_CIRCLE = N_BOTS // len(RADII)

def gen_address(i: int) -> str:
    return f"AAAAAAAAAAAA{i:04X}"

def normalize_theta(t: float) -> float:
    """Normalize angle to [0, 2π)."""
    return t % (2 * math.pi)

def generate_circle_toml() -> str:
    blocks = []
    bot_index = 0

    for radius in RADII:
        for i in range(BOTS_PER_CIRCLE):
            angle = 2 * math.pi * i / BOTS_PER_CIRCLE

            x = int(CENTER_X + radius * math.cos(angle))
            y = int(CENTER_Y + radius * math.sin(angle))

            # Clockwise tangential direction
            theta = normalize_theta(angle - math.pi / 2)

            block = f"""[[dotbots]]
address = "{gen_address(bot_index)}"
calibrated = true
pos_x = {x}
pos_y = {y}
theta = {theta:.5f}
"""
            blocks.append(block)
            bot_index += 1

    return "\n".join(blocks)

if __name__ == "__main__":
    toml_str = generate_circle_toml()
    with open(f"double_circle_{N_BOTS}_bots.toml", "w") as f:
        f.write(toml_str)
