#!/bin/sh
export PYTHONPATH="/usr/lib/kp-detector${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m kp_detector "$@"
