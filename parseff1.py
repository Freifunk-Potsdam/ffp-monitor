#!/usr/bin/env python3
from base import *
import json
import glob
import traceback
import time
from xml.etree import ElementTree as ET
from multiprocessing.pool import ThreadPool
from pymongo import MongoClient
from ips import *
from pprint import pprint

class FfXmlParser:
    def __init__(self,mdb,idb):
        self._mdb = mdb
        self._idb = idb

    def parse_file(self,f):
        try:
            ff = open(f,"rt",encoding="UTF-8")
            fdata = ff.read()
            ff.close()
            ip = os.path.basename(f).partition("_")[0]
            xml = ET.fromstring(fdata)
            self.parsef(xml,ip)
            mvf = os.path.join(os.path.dirname(f),"mv",os.path.basename(f))
            os.rename(f,mvf)
#            os.remove(f)
        except Exception as ex:
            print( time.strftime("%c"), f )
            traceback.print_exc()
            try:
                errf = os.path.join(os.path.dirname(f),"err",os.path.basename(f))
                os.rename(f,errf)
            except:
                pass

    def parsef(self,xml,ip):
        sect = "parsef_%s" % xml.tag.lower()
        if hasattr(self,sect):
            return getattr(self,sect)(xml,ip)
        print("%s not implemented." % sect)

    # used up to script v0.9
    def parsef_ffinfo(self,xml,ip):
        self._mdb["tmpnodeinfo"].insert({
            "host":     xml.attrib.get("host"),
            "time":     float(xml.attrib.get("time")),
            "senderip": ip,
            "routes":   self.parse_routes(xml),
            "sysinfo":  self.parse_sysinfo(xml),
        })

    def parsef_ffstat(self,xml,ip):
        host = xml.attrib.get("host")
        time_ = float(xml.attrib.get("time"))
        ntime = int(time_ * 1000000000)

        interfaces = self.parse_ifconfig( xml )
        networks = sorted( self.extract_networks( interfaces ), key = lambda x: x["bits"], reverse = True )
        for iname,iinfo in self.parse_iwinfo( xml ).items():
            if iname in interfaces:
                interfaces[iname].update(iinfo)
            else:
                interfaces[iname] = iinfo
        leases = self.parse_dhcp_leases( xml, networks, time_)
        # applying updates to mongodb
        self.update_ipnames(interfaces, host, time_)
        dhcpnets = self.update_dhcpnets( host, time_, leases )
        mdbni = {
            "host": host,
            "time": time_,
            "senderip": ip,
        }
        if len(interfaces) > 0:
            mdbni["ifc"] = interfaces
        tmp = self.parse_sysinfo(xml)
        if len(tmp) > 1:
            mdbni["sysinfo"] = tmp
        routes = self.parse_routes(xml)
        if routes is not None:
            tnl = self.parse_iptnl(xml)
            for tn,t in tnl.items():
                t["default"] = tn in routes
                if tn in routes:
                    routes.remove(tn)
            mdbni["sgwroutes"] = tnl
            mdbni["routes"] = routes
        self._mdb["tmpnodeinfo"].insert( mdbni )
        # collecting influx data points
        tags = {
            "hostname":host,
        }
        idps = []
        idps.extend( self.mk_idp( "load", ntime, tags, self.parse_uptime(  xml ) ) )
        idps.extend( self.mk_idp( "cpu",  ntime, tags, self.parse_top_cpu( xml ) ) )
        idps.extend( self.mk_idp( "mem",  ntime, tags, self.parse_top_mem( xml ) ) )
        idps.extend( self.mk_idp( "conn", ntime, tags, self.parse_conn(    xml ) ) )
        idps.extend( self.mk_idps( "fs",       ntime, tags, self.parse_df( xml ) ) )
        idps.extend( self.mk_idps( "network",  ntime, tags, self.mk_idps_network(  interfaces ) ) )
        idps.extend( self.mk_idps( "wireless", ntime, tags, self.mk_idps_wireless( interfaces ) ) )
        idps.extend( self.mk_idps( "dhcp",     ntime, tags, self.mk_idps_dhcp( leases, dhcpnets ) ) )
        idps.extend( self.mk_idps( "links",    ntime, tags, self.mk_idps_links( self.parse_links(xml) ) ) )
        # feeding influx data
        self._idb.write_points(idps)


    def update_ipnames(self, interfaces, host, ts):
        for i in interfaces.values():
            if isffip( i.get("addr","") ):
                ns = list( self._mdb["names"].find({"localIP": i["addr"]}) )
                if len(ns) > 1:
                    self._mdb["names"].remove({"localIP": i["addr"]})
                elif len(ns) == 1 and ns[0].get("last_seen",0) > ts:
                    break
                self._mdb["names"].update(
                    { "localIP": i["addr"], },
                    {
                        "$setOnInsert": { "localIP": i["addr"] },
                        "$set": { "hostname": host, "last_seen": ts },
                    },
                    upsert = True
                )

    def update_dhcpnets(self, host, ts, leases):
        for n,l in leases.items():
            if l > 0:
                self._mdb["networks"].update(
                    {"hostname":host},
                    {
                        "$setOnInsert":{"hostname":host},
                        "$addToSet":{"networks":n},
                    },
                    upsert = True)
        dhcpnets = self._mdb["networks"].find_one({"hostname":host})
        return [] if dhcpnets is None else dhcpnets.get("networks",[])
    
    def mk_idps_links(self, links):
        for l in links:
            yield ({
                "localIP":              l["localIP"],
                "remoteIP":             l["remoteIP"],
                "remoteHostname":       l["remoteHostname"],
            },{
                "linkQuality":          l["linkQuality"],
                "neighborLinkQuality":  l["neighborLinkQuality"],
                "linkCost":             l["linkCost"],
            })

    def mk_idps_dhcp(self, leases, dhcpnets):
        for n,l in leases.items():
            if l > 0 or n in dhcpnets:
                yield ( {"network":n}, {"leases":l} )

    def mk_idps_network(self,interfaces):
        for n,i in interfaces.items():
            tags = {}
            fields = {}
            for t in ["device","addr","mask","net"]:
                if t in i:
                    tags[t] = i[t]
            for f in ["rx_packets","tx_packets","rx_bytes","tx_bytes"]:
                if f in i:
                    fields[f] = i[f]
            yield ( tags, fields )

    def mk_idps_wireless(self,interfaces):
        for n,i in interfaces.items():
            fields = {}
            if set(i.keys()) >= set([ "device", "essid", "assoc" ]):
                tags = { "device": i["device"] }
                tags["essid"] = i["essid"]
                fields["assoc"] = i["assoc"]
                yield ( tags, fields )

    def mk_idps(self, meas, ts, tagsa, tags_fields):
        for tags,fields in tags_fields:
            tags.update(tagsa)
            if len(fields) > 0:
                yield {
                    "measurement":  meas,
                    "timestamp":    ts,
                    "tags":         tags,
                    "fields":       fields,
                }

    def mk_idp(self, meas, ts, tags, fields):
        if len(fields) > 0:
            yield {
                "measurement":  meas,
                "timestamp":    ts,
                "tags":         tags,
                "fields":       fields,
            }

    def parse_routes(self,xml):
        res = None
        for r in xml.findall("routes"):
            res = [] if res is None else res
            for r in r.text.strip().split("\n"):
                if r.strip() != "":
                    res.append(r.split()[2])
        return res

    def parse_iptnl(self,xml):
        iptnl = {}
        for t in xml.findall("tunnel"):
            for t in t.text.strip().split("\n"):
                if t.startswith("tnl_"):
                    t = t.split()
                    if t[2] == "remote":
                        iptnl[ t[0].strip(":") ] = {"remote": t[3]}
        return iptnl

    def parse_sysinfo(self,xml):
        res = {"script":xml.attrib.get("ver","")}
        for o in xml.findall("options"):
            for o in o.text.strip().split("\n"):
                if o.strip() != "":
                    o = o.strip().split(None,2)
                    res[o[1].strip().lower()] = o[2].strip().strip("'\"")
        for i in xml.findall("system"):
            for i in i.text.strip().split("\n"):
                i = i.split(":",1)
                res[i[0].strip().lower()] = i[1].strip()
        return res

    def parse_uptime(self,xml):
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
        return fields

    def parse_top_cpu(self,xml):
        fields = {}
        for t in xml.findall("top"):
            t = t.text.strip().split("\n")
            m = t[0].split()[1:]
            c = t[1].split()[1:]
            for i in range(len(c)//2):
                fields["cpu_%s" % (c[i*2+1])] = int(c[i*2].strip("%"))
        return fields

    def parse_top_mem(self,xml):
        fields = {}
        for t in xml.findall("top"):
            t = t.text.strip().split("\n")
            m = t[0].split()[1:]
            c = t[1].split()[1:]
            for i in range(len(m)//2):
                fields["mem_%s" % (m[i*2+1].strip(","))] = int(m[i*2].strip("K"))
        return fields

    def parse_conn(self,xml):
        fields = {
            "conn_tcp": 0,
            "conn_udp": 0,
            "conn_icmp": 0,
            "conn_unknown": 0,
        }
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
        return fields

    def parse_ifconfig(self,xml):
        bridges = {}
        for brc in xml.findall("brctl"):
            br = None
            for l in brc.text.strip().split("\n")[1:]:
                l = l.strip().split()
                if len(l) > 1:
                    br = l[0]
                    bridges[ br ] = [ l[-1] ]
                elif len(l) == 1 and br is not None:
                    bridges[ br ].append(l[-1])
        interfaces = {}
        for ifc in xml.findall("ifconfig"):
            for i in ifc.findall("*"):
                i = [x.strip() for x in i.text.strip().split("\n")]
                if len(i) > 0 and len(i[0]) > 0:
                    name = i[0].split()[0].replace(".","_")
                    if name not in interfaces:
                        l = i[0].split()
                        interfaces[name] = {"device":l[0]}
                        if "HWaddr" in l:
                            interfaces[name]["mac"] = l[ l.index("HWaddr") + 1 ]
                        if l[0] in bridges:
                            interfaces[name]["brports"] = bridges[ l[0] ]
                        else:
                            for br,brports in bridges.items():
                                if l[0] in brports:
                                    interfaces[name]["bridge"] = br
                    for l in i[1:]:
                        l = l.split()
                        if l[0] == "inet":
                            for l in l[1:]:
                                a,_,v = l.partition(":")
                                interfaces[name][a.lower()] = v
                        elif l[0] == "RX" and l[1].startswith("packets:"):
                            interfaces[name]["rx_packets"] = int(l[1].partition(":")[2])
                        elif l[0] == "TX" and l[1].startswith("packets:"):
                            interfaces[name]["tx_packets"] = int(l[1].partition(":")[2])
                        elif l[0] == "RX" and l[1].startswith("bytes:"):
                            interfaces[name]["rx_bytes"] = int(l[1].partition(":")[2])
                            l = l[l.index("TX"):]
                            interfaces[name]["tx_bytes"] = int(l[1].partition(":")[2])
        return interfaces

    def parse_iwinfo(self,xml):
        interfaces = {}
        for iwi in xml.findall("iwinfo"):
            # new format
            for i in iwi.findall("*"):
                i = [x.strip() for x in i.text.strip().split("\n")]
                if len(i) > 0 and len(i[0]) > 0:
                    name = i[0].split()[0].replace(".","_")
                    if name not in interfaces:
                        l = i[0].split()
                        interfaces[name] = {"device":l[0]}
                        if "ESSID:" in l:
                            interfaces[name]["essid"] = " ".join( l[ l.index("ESSID:") + 1: ] ).strip('"')
                    for l in i[1:]:
                        if l.startswith("Access Point:"):
                            interfaces[name]["bssid"] = l.split()[2]
                        elif l.startswith("Assoc:"):
                            interfaces[name]["assoc"] = int(l.split()[1])
                        elif l.startswith("Mode:"):
                            interfaces[name]["mode"] = l.split()[1]
                            interfaces[name]["channel"] = l.split()[3]
                            interfaces[name]["freq"] = l.split()[4].strip("()")
                        elif l.startswith("Tx-Power:"):
                            interfaces[name]["txpower"] = int(l.split()[1])
                        elif l.startswith("Encryption:"):
                            interfaces[name]["encryption"] = l.split()[1]
            if len(interfaces) == 0:
                # old format
                for l in iwi.text.strip().split("\n"):
                    l = l.split()
                    if len(l) >= 4:
                        if l[0] not in interfaces:
                            interfaces[l[0]] = {}
                        interfaces[l[0]]["essid"] = " ".join(l[2:-1]).strip('"')
                        interfaces[l[0]]["assoc"] = int(l[-1])
        return interfaces

    def extract_networks(self,interfaces):
        for i in interfaces.values():
            if "addr" in i and "mask" in i:
                i["net"],bits = calcnet(i["addr"],i["mask"])
                if bits > 16:
                    yield {
                        "bits": bits,
                        "net":  i["net"],
                        "mask": i["mask"],
                    }

    def parse_dhcp_leases(self, xml, networks, ts):
        leases = {}
        for n in networks:
            leases["%s/%d" % ( n["net"], n["bits"] )] = 0
        for dl in xml.findall("dhcp_leases"):
            dl = [x.strip().split() for x in dl.text.strip().split("\n")]
            for l in dl:
                if len(l) > 1 and float(l[0]) >= ts:
                    for n in networks:
                        if n["net"] == calcnet( l[ 2 if len(l) > 2 else 1 ], n["mask"] )[0]:
                            leases[ "%s/%d" % ( n["net"], n["bits"] ) ] += 1
                            break
        return leases

    def parse_df(self,xml):
        for df in xml.findall("df"):
            df = df.text.strip().split("\n")[1:]
            for l in df:
                l = l.strip().split()
                tags = {}
#                tags["dev"] = l[0]
                tags["mp"] = l[5]
                fields = {
#                    "size":int(l[1]),
                    "used":int(l[2]),
                    "free":int(l[3]),
                }
                yield ( tags, fields )

    def parse_links(self,xml):
        for l in xml.findall("links"):
            if l.text.strip() != "":
                l = json.loads(l.text.strip())
                if "links" in l:
                    for link in l["links"]:
                        n = self._mdb["names"].find_one({"localIP":link["remoteIP"]})
                        rhost = "Unknown" if n is None else n.get("hostname",None)
                        yield {
                            "localIP":              link["localIP"],
                            "remoteIP":             link["remoteIP"],
                            "linkQuality":          float(link["linkQuality"]),
                            "neighborLinkQuality":  float(link["neighborLinkQuality"]),
                            "linkCost":             int(link["linkCost"]),
                            "remoteHostname":       rhost,
                        }

if __name__ == "__main__":
    sys.stderr = sys.stdout

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

    ffxmlp = FfXmlParser( mongodb, influxdb )
    tp = ThreadPool(32)
    for arg in sys.argv[1:]:
        if os.path.isfile( arg ):
            tp.apply_async( ffxmlp.parse_file, [ arg ] )
        elif os.path.isdir( arg ):
            for f in glob.iglob( os.path.join( arg, "*.xml" ) ):
                if time.time() - os.stat(f).st_ctime > 30:
                    tp.apply_async( ffxmlp.parse_file, [ f ] )
        else:
            print("File not found: %s" % arg)
    tp.close()
    tp.join()

    try:
        os.remove(pidf)
    except FileNotFoundError:
        pass
