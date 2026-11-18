#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

#include <librealsense2/rs.hpp>

int main(int argc, char** argv) {
  if (argc != 3) {
    std::cerr << "usage: " << argv[0] << " DURATION_SECONDS OUTPUT.csv\n";
    return 2;
  }
  const double duration = std::stod(argv[1]);
  const std::string output_path = argv[2];
  if (!(duration > 0.0 && duration <= 600.0)) {
    std::cerr << "duration must be in (0, 600]\n";
    return 2;
  }

  try {
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
        if (profile.stream_type() == RS2_STREAM_ACCEL && profile.fps() > accel_fps) {
          accel_profile = profile;
          motion_sensor = sensor;
          accel_fps = profile.fps();
        }
        if (profile.stream_type() == RS2_STREAM_DEPTH) {
          const auto video = profile.as<rs2::video_stream_profile>();
          if (!depth_profile ||
              (video.width() == 640 && video.height() == 480 && profile.fps() == 30)) {
            depth_profile = profile;
          }
        }
      }
    }
    if (!accel_profile) throw std::runtime_error("D435i accelerometer profile not found");
    if (!depth_profile) throw std::runtime_error("D435i depth profile not found");

    const rs2_extrinsics accel_to_depth = accel_profile.get_extrinsics_to(depth_profile);
    std::ofstream out(output_path);
    if (!out) throw std::runtime_error("cannot open output: " + output_path);
    out << "sample,t_host_s,t_sensor_ms,frame_number,ax,ay,az,depth_ax,depth_ay,depth_az\n";
    out << std::fixed << std::setprecision(9);

    const auto start = std::chrono::steady_clock::now();
    size_t sample = 0;
    motion_sensor.open(accel_profile);
    motion_sensor.start([&](rs2::frame frame) {
      const auto motion = frame.as<rs2::motion_frame>();
      if (!motion) return;
      const rs2_vector value = motion.get_motion_data();
      const float source[3] = {value.x, value.y, value.z};
      // Acceleration is a vector, so apply only the extrinsic rotation.  The
      // translation used for transforming 3-D points must not be added here.
      const float transformed[3] = {
          accel_to_depth.rotation[0] * source[0] +
              accel_to_depth.rotation[3] * source[1] +
              accel_to_depth.rotation[6] * source[2],
          accel_to_depth.rotation[1] * source[0] +
              accel_to_depth.rotation[4] * source[1] +
              accel_to_depth.rotation[7] * source[2],
          accel_to_depth.rotation[2] * source[0] +
              accel_to_depth.rotation[5] * source[1] +
              accel_to_depth.rotation[8] * source[2],
      };
      const double t = std::chrono::duration<double>(
          std::chrono::steady_clock::now() - start).count();
      out << sample++ << ',' << t << ',' << frame.get_timestamp() << ','
          << frame.get_frame_number() << ',' << value.x << ',' << value.y << ','
          << value.z << ',' << transformed[0] << ',' << transformed[1] << ','
          << transformed[2] << '\n';
    });

    std::this_thread::sleep_for(std::chrono::duration<double>(duration));
    motion_sensor.stop();
    motion_sensor.close();
    out.flush();
    std::cout << "samples=" << sample << " accel_fps=" << accel_fps
              << " output=" << output_path << '\n';
    return sample > 0 ? 0 : 1;
  } catch (const rs2::error& error) {
    std::cerr << "RealSense error: " << error.what() << '\n';
    return 1;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
