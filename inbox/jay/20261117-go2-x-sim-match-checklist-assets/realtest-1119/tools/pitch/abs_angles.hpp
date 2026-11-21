#pragma once
// 중력 방향 (단위 벡터 · 아래를 가리킴) 에서 각을 읽는다. relative_pitch.hpp 와 같은 축 약속:
//   몸통: Go2 lowstate IMU 사원수로 만든 projected gravity (x 앞 · y 왼 · z 위). 수평이면 (0, 0, -1)
//   카메라: D435i 깊이 광학 틀 (x 오른 · y 아래 · z 앞). 수평 정면이면 (0, 1, 0)
#include <array>
#include <cmath>

inline double rad2deg(double r) { return r * 180.0 / std::acos(-1.0); }
inline double clamp1(double v) { return v > 1.0 ? 1.0 : (v < -1.0 ? -1.0 : v); }

// 몸통 앞숙임 (+ = 코가 아래) · 옆 기울기 (+ = 오른쪽이 아래)
inline double body_pitch_down_deg(const std::array<double, 3>& g) { return rad2deg(std::asin(clamp1(g[0]))); }
inline double body_roll_right_down_deg(const std::array<double, 3>& g) { return rad2deg(std::asin(clamp1(-g[1]))); }
// 카메라 광축이 수평 아래로 숙인 각 (바닥 · 중력 기준 절대각) · 옆 기울기 (+ = 영상 오른쪽이 위)
inline double camera_down_deg(const std::array<double, 3>& g) { return rad2deg(std::asin(clamp1(g[2]))); }
inline double camera_roll_deg(const std::array<double, 3>& g) { return rad2deg(std::atan2(g[0], g[1])); }
