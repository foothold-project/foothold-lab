cmake_minimum_required(VERSION 3.16)
project(go2_measurement_readonly LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

enable_testing()
add_executable(camera_geometry_test camera_geometry_test.cpp)
add_test(NAME camera_geometry_test COMMAND camera_geometry_test)
add_executable(relative_pitch_test relative_pitch_test.cpp)
add_test(NAME relative_pitch_test COMMAND relative_pitch_test)

find_package(unitree_sdk2 REQUIRED)
add_executable(state_capture state_capture.cpp)
target_link_libraries(state_capture PRIVATE unitree_sdk2)

set(RSUSB_ROOT "/home/nvidia/go2_diag/librealsense-rsusb-v2.58.4")
add_executable(depth_capture depth_capture.cpp)
target_include_directories(depth_capture PRIVATE "${RSUSB_ROOT}/include")
target_link_libraries(depth_capture PRIVATE
  "${RSUSB_ROOT}/build-rsusb/Release/librealsense2.so")

find_package(OpenCV REQUIRED COMPONENTS core highgui imgcodecs imgproc)
add_executable(depth_center_snapshot depth_center_snapshot.cpp)
target_include_directories(depth_center_snapshot PRIVATE "${RSUSB_ROOT}/include")
target_link_libraries(depth_center_snapshot PRIVATE
  "${RSUSB_ROOT}/build-rsusb/Release/librealsense2.so"
  ${OpenCV_LIBS})

add_executable(depth_center_live depth_center_live.cpp)
target_include_directories(depth_center_live PRIVATE "${RSUSB_ROOT}/include")
target_link_libraries(depth_center_live PRIVATE
  "${RSUSB_ROOT}/build-rsusb/Release/librealsense2.so"
  ${OpenCV_LIBS})

add_executable(depth_walk_capture depth_walk_capture.cpp)
target_include_directories(depth_walk_capture PRIVATE "${RSUSB_ROOT}/include")
target_link_libraries(depth_walk_capture PRIVATE
  "${RSUSB_ROOT}/build-rsusb/Release/librealsense2.so")

add_executable(d435i_imu_capture d435i_imu_capture.cpp)
target_include_directories(d435i_imu_capture PRIVATE "${RSUSB_ROOT}/include")
target_link_libraries(d435i_imu_capture PRIVATE
  "${RSUSB_ROOT}/build-rsusb/Release/librealsense2.so")
