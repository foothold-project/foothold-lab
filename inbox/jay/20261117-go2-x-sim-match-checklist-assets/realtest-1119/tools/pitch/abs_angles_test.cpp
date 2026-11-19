// g++ -std=c++17 abs_angles_test.cpp -o abs_angles_test && ./abs_angles_test
#include <cassert>
#include <cmath>
#include <cstdio>
#include "abs_angles.hpp"
#include "relative_pitch.hpp"
int main() {
  const double d2r = std::acos(-1.0) / 180.0;
  // 몸통 수평 · 카메라 35° 아래: 절대 35 · 상대 35 · 몸통 0
  std::array<double, 3> level{0, 0, -1};
  auto cam = expected_camera_gravity(level, 35.0);
  assert(std::abs(camera_down_deg(cam) - 35.0) < 1e-9);
  assert(std::abs(body_pitch_down_deg(level)) < 1e-9);
  assert(std::abs(camera_roll_deg(cam)) < 1e-9);
  // 몸통 코가 3.6° 아래 · 장착 35°: 절대 38.6 · 몸통 3.6 · 상대는 35 로 다시 맞춤
  const double t = 3.6 * d2r;
  std::array<double, 3> nose_down{std::sin(t), 0, -std::cos(t)};
  cam = expected_camera_gravity(nose_down, 35.0);
  assert(std::abs(body_pitch_down_deg(nose_down) - 3.6) < 1e-9);
  assert(std::abs(camera_down_deg(cam) - 38.6) < 1e-9);
  auto fit = fit_relative_down_pitch(nose_down, cam);
  assert(std::abs(fit.down_angle_deg - 35.0) < 0.0011);
  // 몸통 오른쪽이 2° 아래
  const double r = 2.0 * d2r;
  std::array<double, 3> roll_r{0, -std::sin(r), -std::cos(r)};
  assert(std::abs(body_roll_right_down_deg(roll_r) - 2.0) < 1e-9);
  std::puts("abs_angles_test ok");
  return 0;
}
