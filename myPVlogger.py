#!/bin/python3

from solarmax_query import SolarMax
import rrdtool
import os
from random import *


class MyPVLogger(SolarMax):
    def __init__(self, host, port, db_name, dry_run=False):
        self.db_name = db_name
        self.dry_run = dry_run

        if not os.path.exists(db_name):
            rrdtool.create(db_name, "--start", "now",
                        "--step", "55",
                        "DS:ac_power:GAUGE:120:0:U",
                        "DS:energy_today:GAUGE:120:0:U",
                        "DS:energy_month:GAUGE:120:0:U",
                        "DS:energy_year:GAUGE:120:0:U",
                        "RRA:AVERAGE:0.5:1:8640",
                        "RRA:AVERAGE:0.5:6:6048",
                        "RRA:AVERAGE:0.5:60:4464")
        try:
            super().__init__(host, port, 0)
        except Exception as e:
            print(f' {e}')
            data="N:0.0:0.0:0:0"
            rrdtool.update(self.db_name, data)
            if not self.dry_run:
                exit(1)

    def push_dummy(self):
        data = "N:" + str(random()) + ":" + \
            str(randint(1,30)) + ":"  \
            + str(randint(5,60)) + ":" \
            + str(randint(7,90))
        print(f'add {data}')
        rrdtool.update(self.db_name, data)

    def push_data(self):
        data = "N:" + str(self.acOutput()) + ":" + \
            str(self.energyDay()) + ":"  \
            + str(self.energyMonth()) + ":" \
            + str(self.energyYear())

        rrdtool.update(self.db_name, data)


def main():
    s = MyPVLogger('192.168.40.210', 12345,
                   "/var/www/solar.rrd")
    if s.dry_run:
        s.push_dummy()
    else:
        s.push_data()


if __name__ == "__main__":
    main()
