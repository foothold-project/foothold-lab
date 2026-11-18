#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <string>
#include <thread>

#include <unitree/idl/go2/LowCmd_.hpp>
#include <unitree/idl/go2/LowState_.hpp>
#include <unitree/idl/go2/SportModeState_.hpp>
#include <unitree/idl/ros2/String_.hpp>
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>

using LowCmd = unitree_go::msg::dds_::LowCmd_;
using LowState = unitree_go::msg::dds_::LowState_;
using SportState = unitree_go::msg::dds_::SportModeState_;
using ErrorString = std_msgs::msg::dds_::String_;

namespace {

constexpr std::array<const char*, 12> kJointNames{
    "FR_hip", "FR_thigh", "FR_calf", "FL_hip", "FL_thigh", "FL_calf",
    "RR_hip", "RR_thigh", "RR_calf", "RL_hip", "RL_thigh", "RL_calf"};

std::mutex sample_mutex;
LowState latest_state;
LowCmd latest_cmd;
SportState latest_sport;
std::atomic<bool> state_ready{false};
std::atomic<bool> cmd_ready{false};
std::atomic<bool> sport_ready{false};
std::atomic<bool> stop_requested{false};
std::atomic<uint64_t> state_callbacks{0};
std::atomic<uint64_t> cmd_callbacks{0};
std::atomic<uint64_t> sport_callbacks{0};
std::atomic<uint64_t> error_callbacks{0};
std::atomic<int64_t> last_state_ns{0};
std::atomic<int64_t> last_cmd_ns{0};
std::atomic<int64_t> last_sport_ns{0};

int64_t steady_now_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}

void on_state(const void* message) {
  std::lock_guard<std::mutex> lock(sample_mutex);
  latest_state = *static_cast<const LowState*>(message);
  ++state_callbacks;
  last_state_ns.store(steady_now_ns(), std::memory_order_release);
  state_ready.store(true, std::memory_order_release);
}

void on_cmd(const void* message) {
  std::lock_guard<std::mutex> lock(sample_mutex);
  latest_cmd = *static_cast<const LowCmd*>(message);
  ++cmd_callbacks;
  last_cmd_ns.store(steady_now_ns(), std::memory_order_release);
  cmd_ready.store(true, std::memory_order_release);
}

void on_sport(const void* message) {
  std::lock_guard<std::mutex> lock(sample_mutex);
  latest_sport = *static_cast<const SportState*>(message);
  ++sport_callbacks;
  last_sport_ns.store(steady_now_ns(), std::memory_order_release);
  sport_ready.store(true, std::memory_order_release);
}

void on_error(const void* message) {
  std::lock_guard<std::mutex> lock(sample_mutex);
  std::cerr << "errorlist_message="
            << static_cast<const ErrorString*>(message)->data() << '\n';
  ++error_callbacks;
}

void on_signal(int) { stop_requested.store(true); }

}  // namespace

int main(int argc, char** argv) {
  if (argc != 4) {
    std::cerr << "usage: " << argv[0]
              << " NETWORK_INTERFACE DURATION_SECONDS OUTPUT.csv\n";
    return 2;
  }

  const std::string interface = argv[1];
  const double duration_seconds = std::stod(argv[2]);
  const std::string output_path = argv[3];
  if (!(duration_seconds > 0.0 && duration_seconds <= 1800.0)) {
    std::cerr << "duration must be in (0, 1800]\n";
    return 2;
  }

  std::signal(SIGINT, on_signal);
  std::signal(SIGTERM, on_signal);

  unitree::robot::ChannelFactory::Instance()->Init(0, interface);
  unitree::robot::ChannelSubscriber<LowState> state_subscriber("rt/lowstate");
  unitree::robot::ChannelSubscriber<LowCmd> cmd_subscriber("rt/lowcmd");
  unitree::robot::ChannelSubscriber<SportState> sport_subscriber(
      "rt/sportmodestate");
  unitree::robot::ChannelSubscriber<ErrorString> error_subscriber(
      "rt/errorlist");
  state_subscriber.InitChannel(on_state, 1);
  cmd_subscriber.InitChannel(on_cmd, 1);
  sport_subscriber.InitChannel(on_sport, 1);
  error_subscriber.InitChannel(on_error, 1);

  for (int i = 0; i < 100 && !state_ready.load(std::memory_order_acquire); ++i) {
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  if (!state_ready.load(std::memory_order_acquire)) {
    std::cerr << "no rt/lowstate received within 5 seconds\n";
    return 1;
  }

  std::ofstream out(output_path);
  if (!out) {
    std::cerr << "cannot open output: " << output_path << '\n';
    return 1;
  }

  out << "sample,t_s,state_callbacks,cmd_callbacks,sport_callbacks,"
         "error_callbacks,state_age_ms,cmd_age_ms,sport_age_ms,"
         "soc_pct,power_v,power_a,bms_status,"
         "sport_error_code,sport_mode,gait_type,body_height";
  for (const auto* name : kJointNames) out << ",temp_" << name;
  for (const auto* name : kJointNames) out << ",reserve0_" << name;
  for (const auto* name : kJointNames) out << ",lost_" << name;
  for (const auto* name : kJointNames) out << ",q_" << name;
  for (const auto* name : kJointNames) out << ",dq_" << name;
  for (const auto* name : kJointNames) out << ",kp_" << name;
  for (const auto* name : kJointNames) out << ",kd_" << name;
  for (const auto* name : kJointNames) out << ",qcmd_" << name;
  out << '\n' << std::fixed << std::setprecision(9);

  const auto start = std::chrono::steady_clock::now();
  const auto period = std::chrono::milliseconds(20);
  const auto requested_samples = static_cast<uint64_t>(
      std::llround(duration_seconds * 50.0));
  auto next = start;
  uint64_t samples_written = 0;
  const float nan = std::numeric_limits<float>::quiet_NaN();

  for (uint64_t sample = 0;
       sample < requested_samples && !stop_requested.load(); ++sample) {
    next += period;
    LowState state;
    LowCmd cmd;
    SportState sport;
    bool have_cmd = false;
    bool have_sport = false;
    {
      std::lock_guard<std::mutex> lock(sample_mutex);
      state = latest_state;
      have_cmd = cmd_ready.load(std::memory_order_acquire);
      have_sport = sport_ready.load(std::memory_order_acquire);
      if (have_cmd) cmd = latest_cmd;
      if (have_sport) sport = latest_sport;
    }

    const double t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - start).count();
    const int64_t now_ns = steady_now_ns();
    const int64_t state_ns = last_state_ns.load(std::memory_order_acquire);
    const int64_t cmd_ns = last_cmd_ns.load(std::memory_order_acquire);
    const int64_t sport_ns = last_sport_ns.load(std::memory_order_acquire);
    const double state_age_ms = state_ns ? (now_ns - state_ns) / 1.0e6 : nan;
    const double cmd_age_ms = cmd_ns ? (now_ns - cmd_ns) / 1.0e6 : nan;
    const double sport_age_ms = sport_ns ? (now_ns - sport_ns) / 1.0e6 : nan;
    const auto& bms = state.bms_state();
    out << sample << ',' << t << ',' << state_callbacks.load() << ','
        << cmd_callbacks.load() << ',' << sport_callbacks.load() << ','
        << error_callbacks.load() << ',' << state_age_ms << ',' << cmd_age_ms
        << ',' << sport_age_ms << ',' << static_cast<unsigned>(bms.soc()) << ','
        << state.power_v() << ',' << state.power_a() << ','
        << static_cast<unsigned>(bms.status()) << ','
        << (have_sport ? sport.error_code() : 0) << ','
        << (have_sport ? static_cast<unsigned>(sport.mode()) : 0) << ','
        << (have_sport ? static_cast<unsigned>(sport.gait_type()) : 0) << ','
        << (have_sport ? sport.body_height() : nan);
    for (int i = 0; i < 12; ++i)
      out << ',' << static_cast<unsigned>(state.motor_state()[i].temperature());
    for (int i = 0; i < 12; ++i)
      out << ',' << static_cast<int64_t>(state.motor_state()[i].reserve()[0]);
    for (int i = 0; i < 12; ++i)
      out << ',' << state.motor_state()[i].lost();
    for (int i = 0; i < 12; ++i) out << ',' << state.motor_state()[i].q();
    for (int i = 0; i < 12; ++i) out << ',' << state.motor_state()[i].dq();
    for (int i = 0; i < 12; ++i)
      out << ',' << (have_cmd ? cmd.motor_cmd()[i].kp() : nan);
    for (int i = 0; i < 12; ++i)
      out << ',' << (have_cmd ? cmd.motor_cmd()[i].kd() : nan);
    for (int i = 0; i < 12; ++i)
      out << ',' << (have_cmd ? cmd.motor_cmd()[i].q() : nan);
    out << '\n';
    ++samples_written;

    if (sample % 50 == 0) {
      uint8_t max_temp = 0;
      int max_index = 0;
      unsigned reserve_nonzero = 0;
      float max_kp = 0.0f;
      float max_kd = 0.0f;
      for (int i = 0; i < 12; ++i) {
        if (state.motor_state()[i].temperature() > max_temp) {
          max_temp = state.motor_state()[i].temperature();
          max_index = i;
        }
        if (state.motor_state()[i].reserve()[0] != 0) ++reserve_nonzero;
        if (have_cmd) {
          max_kp = std::max(max_kp, cmd.motor_cmd()[i].kp());
          max_kd = std::max(max_kd, cmd.motor_cmd()[i].kd());
        }
      }
      std::cerr << std::fixed << std::setprecision(1) << "t=" << t
                << "s soc=" << static_cast<unsigned>(bms.soc())
                << "% FR_hip="
                << static_cast<unsigned>(state.motor_state()[0].temperature())
                << "C FL_hip="
                << static_cast<unsigned>(state.motor_state()[3].temperature())
                << "C max=" << static_cast<unsigned>(max_temp) << "C("
                << kJointNames[max_index] << ") reserve0_nonzero="
                << reserve_nonzero << " kp_max=" << max_kp
                << " kd_max=" << max_kd << " sport_marker="
                << (have_sport ? sport.error_code() : 0)
                << " state_age_ms=" << state_age_ms
                << " cmd_age_ms=" << cmd_age_ms
                << " state_cb=" << state_callbacks.load()
                << " cmd_cb=" << cmd_callbacks.load()
                << " errorlist_messages=" << error_callbacks.load() << '\n';
      out.flush();
    }
    std::this_thread::sleep_until(next);
  }

  out.flush();
  std::cout << "samples=" << samples_written
            << " state_callbacks=" << state_callbacks.load()
            << " cmd_callbacks=" << cmd_callbacks.load()
            << " sport_callbacks=" << sport_callbacks.load()
            << " error_callbacks=" << error_callbacks.load()
            << " output=" << output_path << '\n';
  return 0;
}
