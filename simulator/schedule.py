"""When each row is sent, in seconds after the run starts.

- fixed:  a steady `rate` rows per second (row n at n / rate).
- replay: the real gaps between the dataset's `Time` values, divided by `speed`
          (speed 10 = ten times faster than the transactions really happened).

The schedule is fixed up front ("open loop"): a slow response doesn't push later
sends back, so the rate you ask for is the rate the API gets, unless the
concurrency limit is reached (then the run reports the slower actual rate).
"""
MODES = ("fixed", "replay")


def send_offsets(times: list[float], mode: str, rate: float, speed: float) -> list[float]:
    if mode == "fixed":
        if rate <= 0:
            raise ValueError("rate must be > 0")
        return [i / rate for i in range(len(times))]
    if mode == "replay":
        if speed <= 0:
            raise ValueError("speed must be > 0")
        start = times[0] if times else 0.0
        return [(t - start) / speed for t in times]
    raise ValueError(f"mode must be one of {MODES}")
