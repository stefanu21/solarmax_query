#!/bin/python3

from solarmax_query import SolarMax
import os, time, calendar
from random import *
import requests
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import logging
from systemd.journal import JournalHandler
from datetime import timedelta
import re

CRONE_INTERVAL=60

logg = logging.getLogger("mySolarLogger")
journal_handler = JournalHandler()
journal_handler.setFormatter(logging.Formatter("[%(levelname)s]: %(message)s")) 
logg.addHandler(journal_handler)
logg.setLevel(logging.DEBUG)

class MyTasmotaConsumers():
    def __init__(self, devices:dict):
        self.devices = devices
        self.status_values = [ ["Total", "kWh"], ["Yesterday", "kWh"], ["Today", "kWh"], ["Power", "W"]]

    def get_req(self, ip, param):
        return requests.get("http://" + ip + "/cm?cmnd=" + param).json()

    def get_uptime(self, device):
        uptime_re = re.compile(r'^(\d+)T(\d+):(\d+):(\d+)$')
        r = self.get_req(self.devices.get(device), "STATE")['Uptime']
        m = uptime_re.match(r)
        if m:
            return timedelta(
                    days=int(m.group(1)),
                    hours=int(m.group(2)),
                    minutes=int(m.group(3)),
                    seconds=int(m.group(4))).total_seconds()
        return -1

    def get_consumption(self, device=None):
        c = []
        for k,v in self.devices.items():
            try:
                if device and device != k:
                    continue
                d = {}
                r = self.get_req(v, "STATUS+10")
                for i in self.status_values:
                    d[i[0]]= r["StatusSNS"]["ENERGY"][i[0]]
                
                d['created'] = calendar.timegm(time.gmtime())
                d['name'] = k
                c.append(d)
                logg.info(d)
            except Exception as e:
                logg.exception("Error %s", e)
        return c

    def set_energy_today(self, device, val):
        return self.get_req(self.devices.get(device), "EnergyToday1%20" + str(val))
    
    def set_energy_yesterday(self, device, val):
        return self.get_req(self.devices.get(device), "EnergyYesterday1%20" + str(val))

    def set_energy_total(self, device, val):
        return self.get_req(self.devices.get(device), "EnergyTotal1%20" + str(val))

    def turn_on(self, device=None):
        return self.get_req(self.devices.get(device), "Power%20On")

    def turn_off(self, device=None):
        return self.get_req(self.devices.get(device), "Power%20Off")

class MyS0Consumers():
    def __init__(self, devices:dict, ip):
        self.devices = devices
        self.ip = ip
        self.status_values = [ ["energy", "Wh"], ["power", "Wh"]]

    def get_req(self, param):
        return requests.get("http://" + self.ip + "/S0?pin=" + param).json()

    def get_consumption(self, device=None):
        c = []
        for k,v in self.devices.items():
            try:
                if device and device != k:
                    continue
                d = {}
                r = self.get_req(v)
                for i in self.status_values:
                    d[i[0]]= r[i[0]]
                
                d['created'] = calendar.timegm(time.gmtime())
                d['name'] = k
                c.append(d)
                logg.info(d)
            except Exception as e:
                logg.exception("Error %s", e)
        return c

class MyProducers(SolarMax):
    def __init__(self, host, port, db_name, dry_run=False):
        self.db_name = db_name
        self.dry_run = dry_run
        super().__init__(host, port, 0)

    def get_production(self):
        d = dict();
        d['today'] = self.energyDay()
        d['month'] = self.energyMonth()
        d['year'] = self.energyYear()
        d['power'] = self.acOutput()
        d['name'] = self.model()
        d['created'] = calendar.timegm(time.gmtime())
        return d


class MyDB():
    def __init__(self, token, org, bucket):
        self._org=org
        self._bucket=bucket
        self._client = InfluxDBClient(url='http://localhost:8086', token=token)

    def write_data(self, data, keys=["today", "month", "year","power"]):
        p = Point.from_dict(data,
                write_precision=WritePrecision.S,
                record_measurement_key="name",
                record_field_keys=keys,
                record_time_key="created")

        with self._client.write_api(write_options=SYNCHRONOUS) as w:
            w.write(self._bucket, self._org, p)

    def query_data(self, bucket, device, field, start, last=False):
        try:
            q_api = self._client.query_api()

            q = 'from(bucket:"' + bucket + '") \
                    |> range(start: ' + start + ') \
                    |> filter(fn: (r) => r._measurement == "' + device + '" and r._field == "' + field + '")'
            
            if last:
                q = q + '|> last()'

            tables = q_api.query(org=self._org, query=q)
            item = {}
            item['field'] = field
            item['values'] = []

            if last:
                item['value'] = tables[0].records[0].get_value()
                return item

            for r in tables[0].records:
                item['values'].append((r.get_value(), r.get_time()))
            return item
        except Exception as e:
            logg.exception("Error %s", e)
            return None

def main():
    try:
        s = MyProducers('192.168.40.210', 12345,
                       "/var/www/solar_new.rrd", dry_run=True)
        logg.info(s.get_production())  #{'SolarMax 15MT T2': {'today': (43.9, 'kWh'), 'month': (63, 'kWh'), 'year': (2494, 'kWh')}}

        db = MyDB('token_foo', '', 'solar')
        db.write_data(s.get_production())
    
    except Exception as e:
        logg.exception("Error %s", e)

    try:
        tasmota = {
            "tv": "192.168.40.254",
            "freezer": "192.168.40.106",
            "washer": "192.168.40.17",
            "boiler": "192.168.40.94",
        }
        c = MyTasmotaConsumers(tasmota)
        
        db = MyDB('token_foo', '', 'consumer')

        for k,v in c.devices.items():
            try:
                uptime_sec=c.get_uptime(k)
                logg.info("Uptime: %s --> %d sec", k, c.get_uptime(k))
                if uptime_sec >= 0 and uptime_sec < CRONE_INTERVAL:
                    last_tot = db.query_data(db._bucket, k, 'Total', '-10d', True)
                    logg.warn("%s - restart detected set last captured db value %d wh", k, last_tot['value'] * 1000)
                    c.set_energy_today(k, 0)
                    c.set_energy_yesterday(k, 0)
                    c.set_energy_total(k, last_tot['value'] * 1000)
            except:
                pass 

        for item in c.get_consumption():
            last_tot = db.query_data(db._bucket, item['name'], 'Total', '-10d', True)
            if last_tot:
                delta = abs(last_tot['value'] - item['Total'])
                logg.info("[%s] delta %f", item['name'], delta);
                if delta > 0.100:
                    logg.critical("jump detected %s %d Wh", item['name'], delta )
                    item['Total'] = last_tot['value']
                    c.set_energy_today(item['name'], 0)
                    c.set_energy_yesterday(item['name'], 0)
                    c.set_energy_total(item['name'], last_tot['value'] * 1000)

            db.write_data(item, keys=['Total', 'Yesterday', 'Today', 'Power'])
    except Exception as e:
        logg.exception("Error %s", e)
        
    try:
        S0 = {"washer": "13", 
              "freezer": "12"
             }
        c = MyS0Consumers(S0, "192.168.40.238")

        db = MyDB('token_foo', '', 's0')

        for item in c.get_consumption():
            db.write_data(item, keys=['energy','power'])

    except Exception as e:
        logg.exception("Error %s", e)


if __name__ == "__main__":
    main()

