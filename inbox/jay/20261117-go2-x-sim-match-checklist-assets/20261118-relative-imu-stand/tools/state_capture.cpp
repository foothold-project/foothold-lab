#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <string>
#include <thread>

#include <unitree/idl/go2/LowCmd_.hpp>
#include <unitree/idl/go2/LowState_.hpp>
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>

using LowState = unitree_go::msg::dds_::LowState_;
using LowCmd = unitree_go::msg::dds_::LowCmd_;

std::mutex state_mutex;
LowState latest_state;
LowCmd latest_cmd;
std::atomic<bool> state_ready{false};
std::atomic<bool> cmd_ready{false};
std::atomic<uint64_t> state_callbacks{0};
std::atomic<uint64_t> cmd_callbacks{0};

void on_state(const void* message) {
  std::lock_guard<std::mutex> lock(state_mutex);
  latest_state = *static_cast<const LowState*>(message);
  ++state_callbacks;
  state_ready.store(true, std::memory_order_release);
}

void on_cmd(const void* message) {
  std::lock_guard<std::mutex> lock(state_mutex);
  latest_cmd = *static_cast<const LowCmd*>(message);
  ++cmd_callbacks;
  cmd_ready.store(true, std::memory_order_release);
}

std::array<float, 3> projected_gravity(const std::array<float, 4>& q) {
  const float w = q[0];
  const float x = -q[1];
  const float y = -q[2];
  const float z = -q[3];
  return {
      -2.0f * (x * z + w * y),
      -2.0f * (y * z - w * x),
      -(w * w - x * x - y * y + z * z),
  };
}

int main(int argc, char** argv) {
  if (argc != 4) {
    std::cerr << "usage: " << argv[0]
              << " NETWORK_INTERFACE DURATION_SECONDS OUTPUT.csv\n";
    return 2;
  }
  const std::string interface = argv[1];
  const double duration = std::stod(argv[2]);
  const std::string output_path = argv[3];
  if (!(duration > 0.0 && duration <= 600.0)) {
    std::cerr << "duration must be in (0, 600]\n";
    return 2;
  }

  unitree::robot::ChannelFactory::Instance()->Init(0, interface);
  unitree::robot::ChannelSubscriber<LowState> state_sub("rt/lowstate");
  unitree::robot::ChannelSubscriber<LowCmd> cmd_sub("rt/lowcmd");
  state_sub.InitChannel(on_state, 1);
  cmd_sub.InitChannel(on_cmd, 1);

  for (int i = 0; i < 100 && !state_ready.load(std::memory_order_acquire); ++i) {
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  if (!state_ready.load(std::memory_order_acquire)) {
    std::cerr << "no rt/lowstate received within 5 seconds\n";
    return 1;
  }

  std::ofstream out(output_path);
  if (!out) {
    std::cerr << "cannot open output: " << output_path << "\n";
    return 1;
  }
  out << "sample,t_s,source_callbacks,cmd_callbacks,pg_x,pg_y,pg_z,"
         "ang_x,ang_y,ang_z";
  for (int i = 0; i < 12; ++i) out << ",q" << i;
  for (int i = 0; i < 12; ++i) out << ",dq" << i;
  for (int i = 0; i < 12; ++i) out << ",kp" << i;
  for (int i = 0; i < 12; ++i) out << ",kd" << i;
  for (int i = 0; i < 12; ++i) out << ",qcmd" << i;
  out << '\n';
  out << std::fixed << std::setprecision(9);

  const auto start = std::chrono::steady_clock::now();
  const auto period = std::chrono::milliseconds(20);
  auto next = start;
  const size_t samples = static_cast<size_t>(std::llround(duration * 50.0));
  const float nan = std::numeric_limits<float>::quiet_NaN();

  for (size_t sample = 0; sample < samples; ++sample) {
    next += period;
    LowState state;
    LowCmd cmd;
    bool have_cmd = false;
    {
      std::lock_guard<std::mutex> lock(state_mutex);
      state = latest_state;
      have_cmd = cmd_ready.load(std::memory_order_acquire);
      if (have_cmd) cmd = latest_cmd;
    }
    const auto pg = projected_gravity(state.imu_state().quaternion());
    const auto& gyro = state.imu_state().gyroscope();
    const double t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - start).count();
    out << sample << ',' << t << ',' << state_callbacks.load() << ','
        << cmd_callbacks.load() << ',' << pg[0] << ',' << pg[1] << ',' << pg[2]
        << ',' << gyro[0] << ',' << gyro[1] << ',' << gyro[2];
    for (int i = 0; i < 12; ++i) out << ',' << state.motor_state()[i].q();
    for (int i = 0; i < 12; ++i) out << ',' << state.motor_state()[i].dq();
    for (int i = 0; i < 12; ++i) out << ',' << (have_cmd ? cmd.motor_cmd()[i].kp() : nan);
    for (int i = 0; i < 12; ++i) out << ',' << (have_cmd ? cmd.motor_cmd()[i].kd() : nan);
    for (int i = 0; i < 12; ++i) out << ',' << (have_cmd ? cmd.motor_cmd()[i].q() : nan);
    out << '\n';
    std::this_thread::sleep_until(next);
  }

  std::cout << "samples=" << samples << " state_callbacks=" << state_callbacks.load()
            << " cmd_callbacks=" << cmd_callbacks.load() << " output=" << output_path
            << '\n';
  return 0;
}
