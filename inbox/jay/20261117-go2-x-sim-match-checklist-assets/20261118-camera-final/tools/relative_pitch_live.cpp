#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>

#include <librealsense2/rs.hpp>
#include <opencv2/core.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <unitree/idl/go2/LowState_.hpp>
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>

#include "relative_pitch.hpp"

using LowState = unitree_go::msg::dds_::LowState_;

namespace {
std::mutex sample_mutex;
std::array<double, 3> body_filtered{};
std::array<double, 3> camera_filtered{};
uint64_t body_samples = 0;
uint64_t camera_samples = 0;
constexpr double filter_alpha = 0.01;

std::array<double, 3> projected_gravity(const std::array<float, 4>& q) {
  const double w = q[0];
  const double x = -q[1];
  const double y = -q[2];
  const double z = -q[3];
  return {-2.0 * (x * z + w * y), -2.0 * (y * z - w * x),
          -(w * w - x * x - y * y + z * z)};
}

std::array<double, 3> normalized(std::array<double, 3> value) {
  const double norm = std::sqrt(value[0] * value[0] + value[1] * value[1] +
                                value[2] * value[2]);
  if (norm > 0.0) {
    for (double& component : value) component /= norm;
  }
  return value;
}

void on_state(const void* message) {
  const auto& state = *static_cast<const LowState*>(message);
  const auto gravity = projected_gravity(state.imu_state().quaternion());
  std::lock_guard<std::mutex> lock(sample_mutex);
  for (int i = 0; i < 3; ++i) {
    body_filtered[i] = body_samples == 0
                           ? gravity[i]
                           : (1.0 - filter_alpha) * body_filtered[i] +
                                 filter_alpha * gravity[i];
  }
  ++body_samples;
}

std::string number(double value, int precision) {
  std::ostringstream out;
  out << std::fixed << std::setprecision(precision) << value;
  return out.str();
}
}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "usage: " << argv[0] << " NETWORK_INTERFACE\n";
    return 2;
  }
  constexpr double target_deg = 35.0;
  constexpr double tolerance_deg = 0.15;

  try {
    unitree::robot::ChannelFactory::Instance()->Init(0, argv[1]);
    unitree::robot::ChannelSubscriber<LowState> subscriber("rt/lowstate");
    subscriber.InitChannel(on_state, 1);

    rs2::context context;
    const auto devices = context.query_devices();
    if (devices.size() == 0) throw std::runtime_error("no RealSense device");
    const rs2::device device = devices.front();
    rs2::stream_profile accel_profile;
    rs2::stream_profile depth_profile;
    rs2::sensor motion_sensor;
    int accel_fps = -1;
    for (const auto& sensor : device.query_sensors()) {
      for (const auto& profile : sensor.get_stream_profiles()) {
        if (profile.stream_type() == RS2_STREAM_ACCEL &&
            profile.fps() > accel_fps) {
          accel_profile = profile;
          motion_sensor = sensor;
          accel_fps = profile.fps();
        }
        if (profile.stream_type() == RS2_STREAM_DEPTH) {
          const auto video = profile.as<rs2::video_stream_profile>();
          if (!depth_profile || (video.width() == 640 && video.height() == 480 &&
                                 profile.fps() == 30)) {
            depth_profile = profile;
          }
        }
      }
    }
    if (!accel_profile || !depth_profile)
      throw std::runtime_error("D435i accel/depth profile not found");
    const auto extrinsics = accel_profile.get_extrinsics_to(depth_profile);
    motion_sensor.open(accel_profile);
    motion_sensor.start([&](rs2::frame frame) {
      const auto motion = frame.as<rs2::motion_frame>();
      if (!motion) return;
      const auto value = motion.get_motion_data();
      const float source[3] = {value.x, value.y, value.z};
      std::array<double, 3> depth_accel{
          extrinsics.rotation[0] * source[0] +
              extrinsics.rotation[3] * source[1] +
              extrinsics.rotation[6] * source[2],
          extrinsics.rotation[1] * source[0] +
              extrinsics.rotation[4] * source[1] +
              extrinsics.rotation[7] * source[2],
          extrinsics.rotation[2] * source[0] +
              extrinsics.rotation[5] * source[1] +
              extrinsics.rotation[8] * source[2]};
      std::lock_guard<std::mutex> lock(sample_mutex);
      // Accelerometer specific force points opposite projected gravity.
      for (int i = 0; i < 3; ++i) {
        const double projected = -depth_accel[i];
        camera_filtered[i] =
            camera_samples == 0
                ? projected
                : (1.0 - filter_alpha) * camera_filtered[i] +
                      filter_alpha * projected;
      }
      ++camera_samples;
    });

    cv::namedWindow("Go2 D435i relative pitch calibration");
    const auto started = std::chrono::steady_clock::now();
    while (true) {
      std::array<double, 3> body{};
      std::array<double, 3> camera{};
      uint64_t n_body = 0;
      uint64_t n_camera = 0;
      {
        std::lock_guard<std::mutex> lock(sample_mutex);
        body = body_filtered;
        camera = camera_filtered;
        n_body = body_samples;
        n_camera = camera_samples;
      }
      cv::Mat canvas(360, 900, CV_8UC3, cv::Scalar(24, 24, 24));
      const double elapsed = std::chrono::duration<double>(
                                 std::chrono::steady_clock::now() - started)
                                 .count();
      if (n_body > 50 && n_camera > 100 && elapsed >= 1.0) {
        body = normalized(body);
        camera = normalized(camera);
        const auto fit = fit_relative_down_pitch(body, camera);
        const double error = fit.down_angle_deg - target_deg;
        const bool on_target = std::abs(error) <= tolerance_deg;
        const cv::Scalar color =
            on_target ? cv::Scalar(0, 255, 0) : cv::Scalar(0, 180, 255);
        std::string instruction = "ON TARGET - HOLD AND TIGHTEN";
        if (error < -tolerance_deg) instruction = "LOWER CAMERA";
        if (error > tolerance_deg) instruction = "RAISE CAMERA";
        cv::putText(canvas, "CAMERA / BODY RELATIVE DOWN PITCH",
                    cv::Point(35, 60), cv::FONT_HERSHEY_SIMPLEX, 0.9,
                    cv::Scalar(255, 255, 255), 2, cv::LINE_AA);
        cv::putText(canvas, number(fit.down_angle_deg, 3) + " deg",
                    cv::Point(35, 155), cv::FONT_HERSHEY_SIMPLEX, 2.2, color, 4,
                    cv::LINE_AA);
        cv::putText(canvas,
                    "target 35.000 deg | error " + number(error, 3) + " deg",
                    cv::Point(35, 215), cv::FONT_HERSHEY_SIMPLEX, 0.8, color, 2,
                    cv::LINE_AA);
        cv::putText(canvas, instruction, cv::Point(35, 285),
                    cv::FONT_HERSHEY_SIMPLEX, 1.0, color, 3, cv::LINE_AA);
        cv::putText(canvas, "q/Esc: quit | keep robot and camera still",
                    cv::Point(35, 335), cv::FONT_HERSHEY_SIMPLEX, 0.6,
                    cv::Scalar(190, 190, 190), 1, cv::LINE_AA);
        std::ofstream status("/tmp/go2-relative-pitch-live.txt");
        status << std::fixed << std::setprecision(6)
               << "relative_down_pitch_deg=" << fit.down_angle_deg << '\n'
               << "error_to_35_deg=" << error << '\n'
               << "residual=" << fit.residual << '\n'
               << "body_samples=" << n_body << '\n'
               << "camera_samples=" << n_camera << '\n'
               << "instruction=" << instruction << '\n';
      } else {
        cv::putText(canvas, "Collecting IMU samples...", cv::Point(35, 180),
                    cv::FONT_HERSHEY_SIMPLEX, 1.1, cv::Scalar(0, 200, 255), 2,
                    cv::LINE_AA);
      }
      cv::imshow("Go2 D435i relative pitch calibration", canvas);
      const int key = cv::waitKey(50);
      if (key == 27 || key == 'q' || key == 'Q') break;
    }
    motion_sensor.stop();
    motion_sensor.close();
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
