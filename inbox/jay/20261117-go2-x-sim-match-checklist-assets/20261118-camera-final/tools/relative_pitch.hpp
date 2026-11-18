#pragma once

#include <array>
#include <cmath>
#include <limits>

struct RelativePitchFit {
  double down_angle_deg;
  double residual;
};

inline std::array<double, 3> expected_camera_gravity(
    const std::array<double, 3>& body_gravity, double down_angle_deg) {
  const double a = down_angle_deg * std::acos(-1.0) / 180.0;
  const double s = std::sin(a);
  const double c = std::cos(a);
  const auto& g = body_gravity;
  return {
      -g[1],
      -g[0] * s - g[2] * c,
      g[0] * c - g[2] * s,
  };
}

inline RelativePitchFit fit_relative_down_pitch(
    const std::array<double, 3>& body_gravity,
    const std::array<double, 3>& camera_gravity) {
  RelativePitchFit best{std::numeric_limits<double>::quiet_NaN(),
                        std::numeric_limits<double>::infinity()};
  // 0.001 degree grid resolution is well below the sensor/noise uncertainty.
  for (int milli_deg = -90000; milli_deg <= 90000; ++milli_deg) {
    const double angle = static_cast<double>(milli_deg) / 1000.0;
    const auto expected = expected_camera_gravity(body_gravity, angle);
    double error2 = 0.0;
    for (int i = 0; i < 3; ++i) {
      const double delta = expected[i] - camera_gravity[i];
      error2 += delta * delta;
    }
    if (error2 < best.residual * best.residual) {
      best = {angle, std::sqrt(error2)};
    }
  }
  return best;
}
