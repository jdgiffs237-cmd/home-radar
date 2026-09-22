Recorded sessions land here.

    python run_live.py --port COM3 --record data/kitchen.log
    python run_live.py --replay data/kitchen.log

Record a few minutes of real returns early — walk through the beam, stand
still, hold up something soft, hold up a flat board. Then you can iterate on
`detect.py` against real data at full speed instead of standing in front of
the sensor while you debug.
