cmake_minimum_required(VERSION 3.16)
project(go2_camera_relative_pitch_live LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(unitree_sdk2 REQUIRED)
find_package(OpenCV REQUIRED COMPONENTS core highgui imgproc)

set(RSUSB_ROOT "/home/nvidia/go2_diag/librealsense-rsusb-v2.58.4"
    CACHE PATH "RSUSB librealsense installation root")

add_executable(relative_pitch_live relative_pitch_live.cpp)
target_include_directories(relative_pitch_live PRIVATE "${RSUSB_ROOT}/include")
target_link_libraries(relative_pitch_live PRIVATE
  unitree_sdk2
  "${RSUSB_ROOT}/build-rsusb/Release/librealsense2.so"
  ${OpenCV_LIBS})
