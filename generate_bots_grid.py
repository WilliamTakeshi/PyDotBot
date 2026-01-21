import math

N_BOTS = 30
MAX_POS = 1_000_000
MARGIN = 50_000  # keep bots away from edges


def gen_address(i: int) -> str:
    """
    Generate a unique, deterministic 16-char hex-like address.
    """
    return f"AAAAAAAAAAAA{i:04X}"


def generate_grid_toml(n_bots: int) -> str:
    """
    Generate a TOML string with n_bots placed on a grid.
    """
    # Grid size
    cols = math.ceil(math.sqrt(n_bots))
    rows = math.ceil(n_bots / cols)

    # Available space
    span_x = MAX_POS - 2 * MARGIN
    span_y = MAX_POS - 2 * MARGIN

    step_x = span_x / max(1, cols - 1)
    step_y = span_y / max(1, rows - 1)

    blocks = []

    for i in range(n_bots):
        row = i // cols
        col = i % cols

        x = int(MARGIN + col * step_x)
        y = int(MARGIN + row * step_y)

        block = f"""[[dotbots]]
address = "{gen_address(i)}"
calibrated = true
pos_x = {x}
pos_y = {y}
theta = 0.0
"""
        blocks.append(block)

    return "\n".join(blocks)


if __name__ == "__main__":
    toml_str = generate_grid_toml(N_BOTS)
    # print(toml_str)

    with open(f"grid_{N_BOTS}_bots.toml", "w") as f:
        f.write(toml_str)
