import random
import string


def random_address(existing: set[str]) -> str:
    """Generate a unique 16-hex-char address."""
    while True:
        addr = "".join(random.choices("0123456789ABCDEF", k=16))
        if addr not in existing:
            existing.add(addr)
            return addr


def generate_dotbots_toml(n: int) -> str:
    """
    Generate a TOML string with `n` dotbots.
    """
    addresses: set[str] = set()
    blocks = []

    for _ in range(n):
        address = random_address(addresses)
        pos_x = random.randint(1, 999_999)
        pos_y = random.randint(1, 999_999)
        theta = round(random.uniform(0.0, 3.14), 5)

        block = f"""[[dotbots]]
address = "{address}"
calibrated = true
pos_x = {pos_x}
pos_y = {pos_y}
theta = {theta}
"""
        blocks.append(block)

    return "\n".join(blocks)


if __name__ == "__main__":
    n = 1000
    toml_str = generate_dotbots_toml(n=n)

    # Print to stdout
    # print(toml_str)

    # Or write to file:
    with open(f"dotbots_generated{n}.toml", "w") as f:
        f.write(toml_str)
