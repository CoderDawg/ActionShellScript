from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MouseMovementProfile:
    duration_curve: tuple[tuple[int, int], ...] = (
        (1, 320),
        (20, 320),
        (40, 180),
        (60, 110),
        (80, 60),
        (100, 24),
    )
    min_steps: int = 1
    max_steps: int = 120
    step_distance_px: int = 8

    def __post_init__(self) -> None:
        if not self.duration_curve:
            raise ValueError("duration_curve must not be empty.")
        if self.min_steps < 1:
            raise ValueError("min_steps must be >= 1.")
        if self.max_steps < self.min_steps:
            raise ValueError("max_steps must be >= min_steps.")
        if self.step_distance_px < 1:
            raise ValueError("step_distance_px must be >= 1.")

        last_speed: int | None = None
        for speed, duration_ms in self.duration_curve:
            if speed < 0 or speed > 100:
                raise ValueError("duration_curve speeds must be between 0 and 100.")
            if duration_ms < 0:
                raise ValueError("duration_curve durations must be >= 0.")
            if last_speed is not None and speed <= last_speed:
                raise ValueError("duration_curve speeds must be strictly increasing.")
            last_speed = speed

    def duration_ms_for_speed(self, speed: int | None) -> int:
        if speed is None:
            return 0

        normalized_speed = max(0, min(100, int(speed)))
        if normalized_speed <= 0:
            return 0

        points = self.duration_curve
        if normalized_speed <= points[0][0]:
            return points[0][1]
        if normalized_speed >= points[-1][0]:
            return points[-1][1]

        for index in range(1, len(points)):
            left_speed, left_duration = points[index - 1]
            right_speed, right_duration = points[index]
            if normalized_speed == right_speed:
                return right_duration
            if normalized_speed < right_speed:
                span = right_speed - left_speed
                if span <= 0:
                    return right_duration
                offset = normalized_speed - left_speed
                fraction = offset / span
                interpolated = left_duration + (right_duration - left_duration) * fraction
                return max(0, int(round(interpolated)))

        return points[-1][1]

    def steps_for_distance(self, distance_px: float) -> int:
        if distance_px <= 0:
            return self.min_steps
        estimated_steps = int(round(distance_px / self.step_distance_px)) or 1
        return max(self.min_steps, min(self.max_steps, estimated_steps))

    @classmethod
    def fast(cls) -> MouseMovementProfile:
        return cls(
            duration_curve=((1, 160), (20, 160), (40, 90), (60, 55), (80, 30), (100, 12)),
        )

    @classmethod
    def balanced(cls) -> MouseMovementProfile:
        return cls()

    @classmethod
    def smooth(cls) -> MouseMovementProfile:
        return cls(
            duration_curve=((1, 500), (20, 500), (40, 280), (60, 170), (80, 95), (100, 40)),
        )

    @classmethod
    def slow(cls) -> MouseMovementProfile:
        return cls(
            duration_curve=((1, 820), (20, 820), (40, 460), (60, 280), (80, 160), (100, 72)),
        )
