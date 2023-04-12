#!/bin/python3

from solarmax_query import SolarMax
import os, time, calendar
from random import *
import requests
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

class MyTasmotaConsumers():
    def __init__(self, devices:dict):
        self.devices = devices
        self.status_values = [ ["Total", "kWh"], ["Yesterday", "kWh"], ["Today", "kWh"], ["Power", "W"]]

    def get_req(self, ip, param):
        try:
            return requests.get("http://" + ip + "/cm?cmnd=" + param).json()
        except Exception as e:
            print(e)
            raise e

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
            except:
                pass
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
    def __init__(self, devices:dict):
        self.devices = devices
        self.status_values = [ ["energy", "Wh"], ["power", "Wh"]]

    def get_consumption(self, device=None):
        status = {}
        for k,v in self.devices.items():
            d={}
            try:
                if device and device != k:
                    continue
                
                r = requests.get("http://" + v["Host"] + "/S0?pin=" + v["Pins"][0]).json()

                for i in self.status_values:
                    d[i[0]]= r["StatusSNS"]["ENERGY"][i[0]],i[1]
            except:
                pass
            
            status[k]=d

        return status


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

    def query_data(self, query):
        q_api = self._client.query_api()
        tables = q_api.query(self._org, query=query)
        res = []
        for t in tables:
            for r in table.records:
                res.append(r.get_value(), r.get_field())
        return res

def main():
    try:
        s = MyProducers('192.168.40.210', 12345,
                       "/var/www/solar_new.rrd", dry_run=True)
        print(s.get_production());  #{'SolarMax 15MT T2': {'today': (43.9, 'kWh'), 'month': (63, 'kWh'), 'year': (2494, 'kWh')}}

        db = MyDB('token_foo', '', 'solar')
        db.write_data(s.get_production())
    
    except Exception as e:
        print(e)

    try:
        tasmota = {
            "tv": "192.168.40.254",
            "freezer": "192.168.40.106",
            "washer": "192.168.40.17",
            "boiler": "192.168.40.94",
        }
        c = MyTasmotaConsumers(tasmota)
        db = MyDB('token_foo', '', 'consumer')
        for c in c.get_consumption():
            db.write_data(c, keys=['Total', 'Yesterday', 'Today', 'Power'])
            print(c)#{'Total': (25.499, 'kWh'), 'Yesterday': (4.247, 'kWh'), 'Today': (0.908, 'kWh'), 'Power': (568, 'W'), 'created': 1680944423, 'name': 'washer'}
    except Exception as e:
        print(e)
        
    S0 = { "washer": {"Host" : "192.168.40.238", "Pins": ["13","14"]}, }
    #TODO add ESP32 SO consumers

if __name__ == "__main__":
    main()

