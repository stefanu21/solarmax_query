#!/bin/bash

RRD=$1

rrdtool graph out.png -a PNG -b 1024 --start -129600 -A \
-u 16000 -t "PV Anlage Dach" -w 600 -h 200 \
DEF:ac=$RRD:ac_power:AVERAGE \
VDEF:acl=ac,LAST \
VDEF:acm=ac,MAXIMUM \
LINE2:ac#ff0000:"AC Power" \
GPRINT:acl:"aktuell\: %5.2lf kW" \
GPRINT:acm:"max\: %5.2lf kW" \

feh out.png
