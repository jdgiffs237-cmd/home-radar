"""
Every tunable number in one place.

If a value here disagrees with the Arduino sketch, the sketch wins for
acquisition and this file wins for interpretation -- so keep them in sync.
"""

# --- physics -----------------------------------------------------------
SPEED_OF_SOUND = 343.0      # m/s at 20 C (68 F).  331.0 + 0.606 * (deg_F - 32) / 1.8
MAX_RANGE_M = 4.0           # HC-SR04 practical ceiling
MIN_RANGE_M = 0.03          # closer than this, the transducer is still ringing
RANGE_RESOLUTION_M = 0.034  # c * 200us / 2 -- your hard floor
BEAMWIDTH_DEG = 30.0        # HC-SR04, roughly. VL53L0X is ~2.

# --- scan geometry -----------------------------------------------------
FOV_MIN_DEG = 0
FOV_MAX_DEG = 180
STEP_DEG = 5
SERVO_ANGLE_OFFSET = 0.0    # mechanical zero correction (see docs/03)
SERVO_SETTLE_MS = 40

N_CELLS = (FOV_MAX_DEG - FOV_MIN_DEG) // STEP_DEG + 1

# --- serial ------------------------------------------------------------
BAUD = 115200
SERIAL_TIMEOUT_S = 2.0

# --- detection ---------------------------------------------------------
# CFAR parameters. See docs/01 section 5 for what these mean.
CFAR_GUARD_CELLS = 1        # cells either side of the CUT to exclude
CFAR_TRAIN_CELLS = 4        # cells either side used to estimate the floor
CFAR_PFA = 1e-3             # target probability of false alarm

# Detections closer together than this are merged into one target.
CLUSTER_RANGE_M = 0.25
CLUSTER_ANGLE_DEG = 15.0

# --- tracking ----------------------------------------------------------
FRAME_TIME_S = 2.0          # measured, not assumed -- time an actual sweep
TRACK_GATE_M = 0.6          # max plot-to-prediction distance to associate
TRACK_ALPHA = 0.5           # alpha-beta filter position gain
TRACK_BETA = 0.2            # ... velocity gain
TRACK_INIT_HITS = 2         # hits before a tentative track is confirmed
TRACK_DROP_MISSES = 3       # consecutive misses before a track is deleted

# --- display -----------------------------------------------------------
PPI_TRAIL_FRAMES = 4        # how many old sweeps to fade behind the live one
