Class:   derived data / analysis output (not source data)
Author:  Claude subagent dispatched by the lead session (d1392bfd), 2026-11-19 06:33
Basis:   ../bag/bag_0.db3 (rosbag2 sqlite3, 330.29 s), ../monitor.csv; script go2x_cam_derive.py in this folder
Summary: D435i depth camera floor plane while standing still: height 0.3716 m, pitch down 38.59 deg, roll +1.89 deg
Status:  done; numbers measured on this recording only (see caveats)

RESULTS (bag-relative seconds; per-frame RANSAC + least-squares refit on every depth frame in the window)

  window            frames  height m (med / p10 / p90)      pitch down deg (med / p10 / p90)  roll deg (med / p10 / p90)   inlier frac  rms resid
  standing 68-98 s  816/816 0.3716 / 0.3714 / 0.3717         38.59 / 38.57 / 38.61             +1.89 / +1.87 / +1.91        0.823        3.5 mm
  sitting  10-55 s  1229/1229 0.1431 / 0.1431 / 0.1432       33.35 / 33.34 / 33.36             -1.94 / -1.96 / -1.92        0.892        3.0 mm

  monitor.csv body_height median: standing 0.3218 m (1500 samples), sitting 0.0694 m (2250 samples)
  camera height minus body_height:  standing +0.0498 m, sitting +0.0738 m
  (min/max over all frames are in floor_summary.json; no frame failed the fit)

FILES

  go2x_cam_derive.py                  the only script used. "floor" subcommand -> floor_*; "media" subcommand -> still_*, *.mp4, media_info.json
                                      run: OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 taskset -c 0-7 \
                                           /home/jay/data/go2x_raw/.venv-rosbags/bin/python go2x_cam_derive.py floor|media
  floor_summary.json                  intrinsics, fit parameters, per-window stats (median/p10/p90/min/max), monitor body_height, failed frames
  floor_standing_68-98s.csv           per-frame fit, standing window (t_s, height_m, pitch_down_deg, roll_deg, inlier_frac,
                                      n_valid, n_inlier, rms_resid_m, inlier_depth_med_m, nx, ny, nz)
  floor_sitting_10-55s.csv            same, sitting window
  floor_overlay_standing_t083.00s.png sanity check: color | depth | depth with floor inliers in green, frame nearest window middle
  floor_overlay_sitting_t032.49s.png  same for sitting
  floor_run.log, media_run.log        console output of the two runs
  color_full.mp4                      whole recording from /camera/camera/color/image_raw/compressed (JPEG), H.264 640x480 30 fps, 330.3 s
  depth_full.mp4                      whole recording from /camera/camera/depth/image_rect_raw, turbo colormap 0-4 m, black = no data,
                                      colour bar at the bottom, H.264 640x480 30 fps, 330.3 s
  media_info.json                     frame counts, max input gap, actual timestamps used for the stills
  still_color_t080s.png / t150s / t250s   nearest color frame (actual t 80.015 / 149.999 / 250.005 s)
  still_depth_t080s.png / t150s / t250s   nearest depth frame with colour bar (actual t 79.985 / 150.001 / 249.974 s)

METHOD

  Time base: bag-relative t = (messages.timestamp - min(timestamp)) * 1e-9. This is the recorder receive time, not
  header.stamp (depth receive time is about 100 ms after header stamp on the first frame).
  Floor fit: depth camera_info K (fx=fy=387.124, cx=319.636, cy=242.064, 640x480, D all zero, image is already rectified).
  Pixels with depth 0.15-4.0 m are deprojected. RANSAC: 400 three-point hypotheses scored on 20000 sampled points,
  inlier |distance| < 2 cm, candidates restricted to normals (oriented toward the camera) with n_y < -0.5,
  i.e. planes facing up within 60 deg of the image "up" axis; the candidate with the most inliers wins. Then 3 rounds of
  least-squares refit on all valid pixels (normal = smallest eigenvector of the 3x3 inlier covariance).
  Height = distance from the camera optical centre to the plane. inlier_frac = inliers / valid pixels (0.15-4 m).
  Synthetic test before use (known plane, 0.3 % depth noise, invalid band, a box): h 0.40/0.15/0.60 m, pitch 30/15/45,
  roll 5/-3/0 were recovered exactly to the printed precision.
  Videos: constant 30 fps; output slot k (t = k/30 s) shows the latest frame with bag t <= slot t, so wall timing
  is preserved and dropped frames show as held frames. The overlay prints the bag t of the frame shown; when it is
  0.2 s or more older than the slot, the text turns red and says "stale". Encoded with the existing static ffmpeg
  binary inside the isaac311 env (imageio_ffmpeg, libx264, crf 23); nothing was installed for it.
  opencv-python-headless was pip-installed into .venv-rosbags (JPEG decode, colormap, text).

CONVENTIONS

  Optical frame (camera_depth_optical_frame): x right, y down, z forward. Floor normal n points from the floor toward
  the camera. pitch_down = asin(-n_z): positive = camera looks down. roll = atan2(n_x, -n_y): positive = right edge of the
  image is higher than the left edge (camera rotated counter-clockwise as seen from behind). Both angles are relative
  to the floor plane, not to gravity; they equal gravity-based angles only if the floor is level.

CAVEATS

  - The robot stood on a quilted fabric mat (grey with white tree prints; see the stills and overlays). The fitted plane is
    the mat's top surface. Mat thickness and how much the feet sink into it are not measured. At t=250 s the robot
    is beside the mat and the bare floor is visible, so a mat thickness check is possible later but was not done here.
  - The black band on the left of every depth frame is normal for the D435i: the left imager sees an area the right one
    cannot, so stereo depth is undefined there. Small black specks are low-texture or occlusion holes.
  - Sitting window: near floor (bottom of the image) is closer than the D435i minimum range and is empty; the fit
    uses the farther part of the floor. A few near-range noise pixels exist bottom-left.
  - camera height minus body_height differs between standing (+0.050 m) and sitting (+0.074 m) because the body pitch
    differs (camera pitch 38.6 vs 33.3 deg) and body_height is the SDK value, not a measured height of the same point.
    It is a convenience difference, not a mount offset.
  - monitor.csv t_s is assumed equal to bag t (monitor started within about 1 s of the bag; not cross-checked).
    Both windows sit in flat stretches of body_height, so a 1 s shift does not change the medians.
  - Small spread (p10-p90 under 0.3 mm and 0.05 deg) is frame-to-frame repeatability of a still robot, not accuracy.
    Absolute accuracy depends on the factory depth calibration (D435i depth error is about 2 % at 2 m; most floor
    inliers are at 0.5-1 m here) and is not measured.
  - Both video streams have one real recording gap at bag t = 302.88 s (color 4.34 s, depth 3.88 s); it shows as a
    red "stale" held frame. Depth has 9150 frames versus 9774 color frames over the same span (shorter sub-0.2 s
    drops are spread across the recording).

EARLIER HANG (cam_floor_local.py in the lead session scratchpad)

  Cause: np.linalg.svd(Q - c0) with the default full_matrices=True. For an N x 3 inlier matrix this also builds the
  N x N U matrix; with N up to 40000 that is 40000^2 * 8 B = 12.8 GB allocated and filled per frame. The high sys
  time is the kernel faulting in those pages (this host has THP madvise and heavy compaction stalls). sqlite,
  deserialization, nonzero, rng.choice and the RANSAC matvecs were each timed and take milliseconds.
  Measured: svd of N x 3 with full_matrices=True takes 0.24 s at N=5000 (U 0.2 GB) and 0.87 s at N=10000 (U 0.8 GB);
  with full_matrices=False at N=40000 it takes 0.003 s. A step-timed probe stalled exactly at the svd line
  (KeyboardInterrupt traceback inside numpy linalg svd). The script prints nothing until the end, so it looked silent.
  Fix used here: normal from np.linalg.eigh of the 3x3 covariance (svd with full_matrices=False would also work).
