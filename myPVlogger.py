#!/bin/python3

from solarmax_query import SolarMax
import rrdtool

class MyPVLogger(SolarMax):
    def __init__(self, host, port, db_name):
        self.db_name = db_name
        super().__init__(host, port, 0)
        rrdtool.create(db_name, "--start", "now",
                       "--step", "60",
                       "DS:ac_power:GAUGE:120:0:20000",
                       "DS:energy_today:GAUGE:120:0:200",
                       "DS:energy_month:GAUGE:120:0:4000",
                       "DS:energy_year:GAUGE:120:0:9000000",
                       "RRA:AVERAGE:0.5:1:8640",
                       "RRA:AVERAGE:0.5:6:6048",
                       "RRA:AVERAGE:0.5:60:4464")

    def push_data(self):
        data = "N:" + str(self.acOutput()) + ":" + \
            str(self.energyDay()) + ":"  \
            + str(self.energyMonth()) + ":" \
            + str(self.energyYear())

        rrdtool.update(self.db_name, data)


def main():
    s = MyPVLogger('192.168.40.210', 12345, "data.rrd")
    s.push_data()


if __name__ == "__main__":
    main()
