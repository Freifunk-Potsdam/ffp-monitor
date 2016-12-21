#!/usr/bin/env python3
from base import *
import json
import glob
import traceback
import time
from xml.etree import ElementTree as ET
from multiprocessing.pool import ThreadPool
from pymongo import MongoClient
from helpers import *

def parse_ffxml(xml,ip,idb,mdb):
    data = []
    if xml.tag.lower() == "ffinfo":
        host = xml.attrib.get("host")
        time_ = float(xml.attrib.get("time"))
        node = mdb["nodes"].find_one({"hostname":host})
        routes = []
        for r in xml.findall("routes"):
            for r in r.text.strip().split("\n"):
                if r.strip() != "":
                    routes.append(r.split()[2])
        sysinfo = {"script":xml.attrib.get("ver","")}
        for o in xml.findall("options"):
            for o in o.text.strip().split("\n"):
                if o.strip() != "":
                    o = o.strip().split(None,2)
                    sysinfo[o[1].strip().lower()] = o[2].strip().strip("'\"")
        for i in xml.findall("system"):
            for i in i.text.strip().split("\n"):
                i = i.split(":",1)
                sysinfo[i[0].strip().lower()] = i[1].strip()
        mdb["nodes"].update({"hostname":host},{"$set":{"routes":routes}})
        if node is not None and sysinfo != node.get("sysinfo",{}):
            mdb["nodes"].update({"hostname":host},{"$set":{"sysinfo":sysinfo}})
    elif xml.tag.lower() == "ffstat":
        host = xml.attrib.get("host")
        uptime = None
        time_ = float(xml.attrib.get("time"))
        ntime = int(time_ * 1000000000)
        tags = {
            "hostname":host,
        }
        for l in xml.findall("links"):
            if l.text.strip() != "":
                l = json.loads(l.text.strip())
                if "links" in l:
                    for link in l["links"]:
                        ttags = tags.copy()
                        ttags["localIP"] = link["localIP"]
                        ttags["remoteIP"] = link["remoteIP"]
                        fields = {
                            "linkQuality":float(link["linkQuality"]),
                            "neighborLinkQuality":float(link["neighborLinkQuality"]),
                            "linkCost":int(link["linkCost"]),
                        }
                        old = mdb["names"].find_and_modify(
                            {"localIP":ttags["localIP"]},
                            {
                                "$setOnInsert":{"localIP":ttags["localIP"]},
                                "$set":{"hostname":host},
                                "$currentDate":{"last_seen":True}
                            },
                            upsert = True,
                            new = False )
                        oldhost = None if old is None else old.get("hostname",None)
                        if oldhost is not None and oldhost != host:
                            print("%s renamed to %s." % (old.get("hostname"),host))
                        mdb["names"].update(
                            {"localIP":ttags["remoteIP"]},
                            {
                                "$setOnInsert":{"localIP":ttags["remoteIP"],"hostname":None},
                            },
                            upsert = True )
                        n = mdb["names"].find_one({"localIP":ttags["remoteIP"]})
                        n = None if n is None else n.get("hostname",None)
                        ttags["remoteHostname"] = "Unknown" if n is None else n
                        data.append({
                            "measurement": "links",
                            "timestamp": ntime,
                            "tags":ttags,
                            "fields":fields,
                        })

        fields = {}
        for u in xml.findall("uptime"):
            u = u.text.strip().split(",")
            fields["load_1"] = float(u[-3].rpartition(":")[2])
            fields["load_5"] = float(u[-2])
            fields["load_15"] = float(u[-1])
            if u[0].endswith("days") or u[0].endswith("day"):
                uptime = int(u[0].split()[2]) * 24 * 60 * 60
                if u[1].endswith("min"):
                    uptime += int(u[1].strip().split()[0]) * 60
                else:
                    u = u[1].partition(":")
                    uptime += int(u[0]) * 60 * 60 + int(u[2]) * 60
            elif u[0].strip().endswith("min"):
                uptime = int(u[0].split()[2]) * 60
            else:
                u = u[0].split()[2].partition(":")
                uptime = int(u[0]) * 60 * 60 + int(u[2]) * 60
            fields["uptime"] = uptime
        if len(fields) > 0:
            data.append({
                "measurement": "load",
                "timestamp": ntime,
                "tags":tags,
                "fields":fields,
            })
        fields = {}
        for t in xml.findall("top"):
            t = t.text.strip().split("\n")
            m = t[0].split()[1:]
            c = t[1].split()[1:]
            for i in range(len(c)//2):
                fields["cpu_%s" % (c[i*2+1])] = int(c[i*2].strip("%"))
        if len(fields) > 0:
            data.append({
                "measurement": "cpu",
                "timestamp": ntime,
                "tags":tags,
                "fields":fields,
            })
        fields = {}
        for t in xml.findall("top"):
            t = t.text.strip().split("\n")
            m = t[0].split()[1:]
            c = t[1].split()[1:]
            for i in range(len(m)//2):
                fields["mem_%s" % (m[i*2+1].strip(","))] = int(m[i*2].strip("K"))
        if len(fields) > 0:
            data.append({
                "measurement": "mem",
                "timestamp": ntime,
                "tags":tags,
                "fields":fields,
            })
        fields = {}
        fields["conn_tcp"] = 0
        fields["conn_udp"] = 0
        fields["conn_icmp"] = 0
        fields["conn_unknown"] = 0
        for c in xml.findall("conn"):
            c = [x.strip().split() for x in c.text.strip().split("\n")]
            for l in c:
                if len(l) >= 2:
                    n,t = l
                    f = "conn_%s" % t.lower()
                    if f in fields:
                        fields[f] += int(n)
                    else:
                        fields["conn_unknown"] += int(n)
        if len(fields) > 0:
            data.append({
                "measurement": "conn",
                "timestamp": ntime,
                "tags":tags,
                "fields":fields,
            })
        interfaces = {}
        ifconf = []
        for ifc in xml.findall("ifconfig"):
            for i in ifc.findall("*"):
                i = [x.strip() for x in i.text.strip().split("\n")]
                if len(i) > 0 and len(i[0]) > 0:
                    name = i[0].split()[0]
                    if name not in interfaces:
                        interfaces[name] = {}
                    for l in i[1:]:
                        l = l.split()
                        if l[0] == "inet":
                            for l in l[1:]:
                                a,_,v = l.partition(":")
                                interfaces[name][a.lower()] = v
                            if len(interfaces[name]) > 0:
                                ni = {"device":name}
                                ni.update(interfaces[name])
                                ifconf.append(ni)
                        elif l[0] == "RX" and l[1].startswith("packets:"):
                            interfaces[name]["rx_packets"] = int(l[1].partition(":")[2])
                        elif l[0] == "TX" and l[1].startswith("packets:"):
                            interfaces[name]["tx_packets"] = int(l[1].partition(":")[2])
                        elif l[0] == "RX" and l[1].startswith("bytes:"):
                            interfaces[name]["rx_bytes"] = int(l[1].partition(":")[2])
                            l = l[l.index("TX"):]
                            interfaces[name]["tx_bytes"] = int(l[1].partition(":")[2])
        mdb["nodes"].update({"hostname":host}, {"$setOnInsert":{
            "hostname":host,
            "last_ts":0,
            "first_seen":time.time(),
        }}, upsert = True)
        mdb["nodes"].update(
            {
                "hostname":host,
                "last_ts":{"$lt":time_}
            },
            {
                "$set":{
                    "interface_config":ifconf,
                    "last_ts":time_,
                    "last_ip":ip,
                },
            }
        )
        if uptime is not None and uptime < 60 * 60 * 24:
            mdb["nodes"].update({"hostname":host},{"$set":{"uptime":uptime}})
        elif uptime is not None:
            mdb["nodes"].update({"hostname":host},{"$max":{"uptime":uptime}})
        networks = []
        for i in interfaces.values():
            if "addr" in i and "mask" in i:
                i["net"],bits = calcnet(i["addr"],i["mask"])
                if bits > 16:
                    networks.append((bits,i["net"],i["mask"]))
        networks.sort(key = lambda x: x[0],reverse=True)
        for iwi in xml.findall("iwinfo"):
            for l in iwi.text.strip().split("\n"):
                l = l.split()
                if len(l) >= 4:
                    if l[0] not in interfaces:
                        interfaces[l[0]] = {}
                    interfaces[l[0]]["essid"] = " ".join(l[2:-1]).strip('"')
                    interfaces[l[0]]["assoc"] = int(l[-1])
        for n,i in interfaces.items():
            ttags = tags.copy()
            fields = {}
            ttags["device"] = n
            for t in ["addr","mask","net"]:
                if t in i:
                    ttags[t] = i[t]
            for f in ["rx_packets","tx_packets","rx_bytes","tx_bytes"]:
                if f in i:
                    fields[f] = i[f]
            if len(fields) > 0:
                data.append({
                    "measurement": "network",
                    "timestamp": ntime,
                    "tags":ttags,
                    "fields":fields,
                })
            ttags = tags.copy()
            fields = {}
            ttags["device"] = n
            if "essid" in i and "assoc" in i:
                ttags["essid"] = i["essid"]
                fields["assoc"] = i["assoc"]
                data.append({
                    "measurement": "wireless",
                    "timestamp": ntime,
                    "tags":ttags,
                    "fields":fields,
                })
        leases = {}
        for b,n,m in networks:
            leases["%s/%d" % (n,b)] = 0
        for dl in xml.findall("dhcp_leases"):
            dl = [x.strip().split() for x in dl.text.strip().split("\n")]
            for l in dl:
                if len(l) > 1 and float(l[0]) >= time_:
                    for b,n,m in networks:
                        if n == calcnet(l[2 if len(l) > 2 else 1],m)[0]:
                            leases["%s/%d" % (n,b)] += 1
                            break
        for n,l in leases.items():
            exists = True
            if l > 0:
                mdb["networks"].update(
                    {"hostname":host},
                    {
                        "$setOnInsert":{"hostname":host},
                        "$addToSet":{"networks":n}
                    },
                    upsert = True)
            if l > 0 or mdb["networks"].find_one({"hostname":host,"networks":n}) is not None:
                ttags = tags.copy()
                fields = {"leases":l}
                ttags["network"] = n
                data.append({
                    "measurement": "dhcp",
                    "timestamp": ntime,
                    "tags":ttags,
                    "fields":fields,
                })
        for df in xml.findall("df"):
            df = df.text.strip().split("\n")[1:]
            for l in df:
                l = l.strip().split()
                ttags = tags.copy()
    #            ttags["dev"] = l[0]
                ttags["mp"] = l[5]
                fields = {
    #                "size":int(l[1]),
                    "used":int(l[2]),
                    "free":int(l[3]),
                }
                data.append({
                    "measurement": "fs",
                    "timestamp": ntime,
                    "tags":ttags,
                    "fields":fields,
                })
    return data

def workfile(f,idb,mdb):
    try:
        if time.time() - os.stat(f).st_ctime > 30:
#            print(f)
            ff = open(f,"rt",encoding="UTF-8")
            fdata = ff.read()
            ff.close()
            ip = os.path.basename(f).partition("_")[0]
            xml = ET.fromstring(fdata)
            data = parse_ffxml(xml,ip,idb,mdb)
            idb.write_points(data)
            os.remove(f)
    except Exception as ex:
        errf = os.path.join(os.path.dirname(f),"err",os.path.basename(f))
        os.rename(f,errf)
        print(f)
        traceback.print_exc()

pidf = "/var/ffdata/parse.pid"
if os.path.isfile(pidf):
    s = os.stat(pidf)
    if s.st_ctime > time.time() - 60 * 60:
        sys.exit()
    else:
        f = open(pidf,"rt")
        pid = int(f.read())
        f.close()
        try:
            os.kill(pid,15)
        except ProcessLookupError:
            pass
        try:
            os.remove(pidf)
        except FileNotFoundError:
            pass
f = open(pidf,"wt")
f.write(str(os.getpid()))
f.close()

tp = ThreadPool(16)
for f in glob.iglob("/var/ffdata/*.xml"):
    tp.apply_async(workfile,[f,influxdb,mongodb])
tp.close()
tp.join()

try:
    os.remove(pidf)
except FileNotFoundError:
    pass
