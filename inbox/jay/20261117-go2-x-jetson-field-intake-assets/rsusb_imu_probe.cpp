#include <librealsense2/rs.hpp>

#include <atomic>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <thread>

int main() {
    try {
        std::atomic<unsigned long> gyro_count{0};
        std::atomic<unsigned long> accel_count{0};
        rs2_vector first_gyro{};
        rs2_vector first_accel{};
        std::atomic<bool> have_gyro{false};
        std::atomic<bool> have_accel{false};

        rs2::pipeline pipeline;
        rs2::config config;
        config.enable_stream(RS2_STREAM_GYRO, RS2_FORMAT_MOTION_XYZ32F, 200);
        config.enable_stream(RS2_STREAM_ACCEL, RS2_FORMAT_MOTION_XYZ32F, 100);

        pipeline.start(config, [&](const rs2::frame& frame) {
            if (!frame.is<rs2::motion_frame>()) return;
            const auto motion = frame.as<rs2::motion_frame>();
            const auto value = motion.get_motion_data();
            const auto stream = frame.get_profile().stream_type();
            if (stream == RS2_STREAM_GYRO) {
                if (!have_gyro.exchange(true)) first_gyro = value;
                ++gyro_count;
            } else if (stream == RS2_STREAM_ACCEL) {
                if (!have_accel.exchange(true)) first_accel = value;
                ++accel_count;
            }
        });

        constexpr double seconds = 5.0;
        std::this_thread::sleep_for(std::chrono::duration<double>(seconds));
        pipeline.stop();

        std::cout << std::fixed << std::setprecision(3)
                  << "gyro_frames=" << gyro_count.load()
                  << " gyro_hz=" << gyro_count.load() / seconds << '\n'
                  << "accel_frames=" << accel_count.load()
                  << " accel_hz=" << accel_count.load() / seconds << '\n';
        if (have_gyro) {
            std::cout << "first_gyro=" << first_gyro.x << ',' << first_gyro.y << ',' << first_gyro.z << '\n';
        }
        if (have_accel) {
            std::cout << "first_accel=" << first_accel.x << ',' << first_accel.y << ',' << first_accel.z << '\n';
        }
        return have_gyro && have_accel ? 0 : 2;
    } catch (const rs2::error& error) {
        std::cerr << "realsense_error=" << error.what() << '\n';
        return 1;
    } catch (const std::exception& error) {
        std::cerr << "error=" << error.what() << '\n';
        return 1;
    }
}
