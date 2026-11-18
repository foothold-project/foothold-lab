#include <array>
#include <cassert>
#include <cmath>

#include "relative_pitch.hpp"

int main() {
  const std::array<double, 3> level_body{0.0, 0.0, -1.0};
  const auto camera35 = expected_camera_gravity(level_body, 35.0);
  assert(std::abs(camera35[0]) < 1e-12);
  assert(std::abs(camera35[1] - std::cos(35.0 * std::acos(-1.0) / 180.0)) < 1e-12);
  assert(std::abs(camera35[2] - std::sin(35.0 * std::acos(-1.0) / 180.0)) < 1e-12);
  const auto fit35 = fit_relative_down_pitch(level_body, camera35);
  assert(std::abs(fit35.down_angle_deg - 35.0) < 0.0011);
  assert(fit35.residual < 1e-6);

  const std::array<double, 3> tilted_body{-0.08, 0.03, -0.996343};
  const auto camera27 = expected_camera_gravity(tilted_body, 27.25);
  const auto fit27 = fit_relative_down_pitch(tilted_body, camera27);
  assert(std::abs(fit27.down_angle_deg - 27.25) < 0.0011);
  assert(fit27.residual < 1e-6);
  return 0;
}
