#!/usr/bin/env python3
from base import *
import time
from twitter import *
import traceback
import random
import datetime
from datetime import date as date
from datetime import datetime as dt
from datetime import timedelta as td
utcoffset = round( (( dt.now() - td(days=1) ) - ( dt.utcnow() - td(days=1) )).total_seconds() / 60 )
random.seed()

from twitter_auth import *

t = Twitter( auth = OAuth( access_token, access_token_secret, consumer_key, consumer_secret ))

def sendtweet(twitter, msg):
    if len(msg) > 140:
        msg = msg[:137] + "..."
    try:
        t.statuses.update( status = msg )
        return True
    except TwitterHTTPError as ex:
        errs = ex.response_data.get("errors",[])
        for err in errs:
            if err.get("code",0) == 187:
                # duplicate, not sending again
                return None
        traceback.print_exc(file=sys.stdout)
        return False

if len(sys.argv) < 2:
    pass
elif sys.argv[1] == "routermsg":
    now = time.time()
    last = mongodb["tweets"].find_one({},sort=[("ctime",-1)])
    last = now - 3600 if last is None else last["ctime"]
    for c in mongodb["changes"].find( { "$and":[ { "time": { "$gt": last } }, { "time": { "$lte": now } } ] }, sort = [("time",1)] ):
        q = {
            "param":c["param"],
            "$and": [
                { "$or": [
                    {"old":{"$exists":False}},
                    {"old":c["old"]},
                ]},
                { "$or": [
                    {"new":{"$exists":False}},
                    {"new":c["new"]},
                ]},
                { "$or": [
                    {"modified":{"$exists":False}},
                    {"modified":{"$in": c.get("detail",{}).get("modified",[]) }},
                ]},
            ],
        }
        tpls = list(mongodb["templates"].find( q ))
        if len(tpls) > 0:
            msg = random.choice(tpls)["msg"].format_map(c)
            if sendtweet(t, msg) is not False:
#                print(msg)
                mongodb["tweets"].insert({ "msg": msg, "sent": now, "ctime": c["time"] })
                break
elif sys.argv[1] == "netstate":
    states = {}
    for s in mongodb["nodes"].distinct("state"):
        states[s] = mongodb["nodes"].find({"state":s}).count()
    states = sorted( states.items(), key = lambda x: x[1], reverse = True )
    msg = "Zum Freifunk Potsdam Netzwerk gehören %d Router, davon sind" % sum([ x[1] for x in states ])
    if len(states) > 1:
        msg += " %d %s" % (states[0][1],states[0][0])
        for s,nr in states[1:-1]:
            msg += ", %d %s" % (nr,s)
        msg += " und %d %s." % (states[-1][1],states[-1][0])
    else:
        msg += " alle %s." % states[0][0]

    for s in sorted(mongodb["nodes"].distinct("state")):
        if s != "online":
            print( "%s:\n%s\n" % ( s, ", ".join([ n["hostname"] for n in mongodb["nodes"].find({"state":s}) ]) ) )
    print()
    print(msg)
    sendtweet(t, msg)

    users = {}
    allusers = {}
    q = 'SELECT mean(leases) \
         FROM freifunk."default".dhcp \
         WHERE time > NOW() - 48h AND time < NOW() - 2h \
         GROUP BY time(5m),network,hostname fill(none)'
    ires = influxdb.query(q)
    for r in ires.get('results',[]):
        for s in r.get('series',[]):
            d = s.get('tags',{})
            cols = s.get('columns',[])
            vals = s.get('values',[])
            if len(cols) * len(vals) > 0:
                vals.sort(key=lambda x: x[cols.index('time')])
                host = d["hostname"]
                for v in vals:
                    time = v[cols.index('time')]
                    ltime = dt.strptime(time,"%Y-%m-%dT%H:%M:%SZ") + td( minutes=utcoffset )
                    if ltime.date() == date.today() - td(days=1):
                        u = float(v[cols.index('mean')])
                        if host not in users:
                            users[host] = {}
                        if time not in users[host]:
                            users[host][time] = {
                                "time": ltime.strftime("%H:%M"),
                                "users":0,
                            }
                        users[host][time]["users"] += u
                        if time not in allusers:
                            allusers[time] = {
                                "time": ltime.strftime("%H:%M"),
                                "users":0,
                            }
                        allusers[time]["users"] += u
    allusers = sorted( allusers.values(), key = lambda x: x["users"] )
    umin = allusers[0]
    umax = allusers[-1]
    urecords = []
    for h in list(users.keys()):
        r = sorted( users[h].values(), key = lambda x: x["users"] )[-1]
        r["host"] = h
        urecords.append( r )
    urecords.sort( key = lambda x: x["users"], reverse = True )

    rx = {}
    tx = {}
    allrx = 0
    alltx = 0
    q = 'SELECT sum("rx_bytes") \
         FROM "traffic_rx" \
         WHERE "device" =~ /(tun0|ffvpn)/ AND time > NOW() - 48h AND time < NOW() - 2h \
         GROUP BY time(1h),hostname fill(none)'
    ires = influxdb_archive.query(q)
    for r in ires.get('results',[]):
        for s in r.get('series',[]):
            d = s.get('tags',{})
            cols = s.get('columns',[])
            vals = s.get('values',[])
            if len(cols) * len(vals) > 0:
                vals.sort(key=lambda x: x[cols.index('time')])
                host = d["hostname"]
                for v in vals:
                    time = v[cols.index('time')]
                    ltime = dt.strptime(time,"%Y-%m-%dT%H:%M:%SZ") + td( minutes=utcoffset )
                    if ltime.date() == date.today() - td(days=1):
                        tr = int(v[cols.index('sum')])
                        if host not in rx:
                            rx[host] = 0
                        rx[host] += tr
                        allrx += tr
    q = 'SELECT sum("tx_bytes") \
         FROM "traffic_tx" \
         WHERE "device" =~ /(tun0|ffvpn)/ AND time > NOW() - 48h AND time < NOW() - 2h \
         GROUP BY time(1h),hostname fill(none)'
    ires = influxdb_archive.query(q)
    for r in ires.get('results',[]):
        for s in r.get('series',[]):
            d = s.get('tags',{})
            cols = s.get('columns',[])
            vals = s.get('values',[])
            if len(cols) * len(vals) > 0:
                vals.sort(key=lambda x: x[cols.index('time')])
                host = d["hostname"]
                for v in vals:
                    time = v[cols.index('time')]
                    ltime = dt.strptime(time,"%Y-%m-%dT%H:%M:%SZ") + td( minutes=utcoffset )
                    if ltime.date() == date.today() - td(days=1):
                        tr = int(v[cols.index('sum')])
                        if host not in tx:
                            tx[host] = 0
                        tx[host] += tr
                        alltx += tr
    traf = []
    for h in set(rx.keys()) | set(tx.keys()):
        traf.append(( h,rx.get(h,0) + tx.get(h,0) ))
    traf.sort( key=lambda x: x[1], reverse = True )
    msg = "Die meisten Clients waren gestern um %s online (%d), die wenigsten um %s (%d). " % \
        ( umax["time"], umax["users"], umin["time"], umin["users"] )
    print(msg)
    sendtweet(t, msg)
    for urec in urecords[:3]:
        msg = "Gestern um %s waren bei %s %d Clients online." % (urec["time"],urec["host"],urec["users"])
        print(msg)
        sendtweet(t, msg)
    for h,tr in traf[:3]:
        msg = "%s hat gestern %s übertragen, davon wurde %s heruntergeladen und %s hochgeladen." % \
            (h, formatBytes(tr,2), formatBytes(rx[h],2), formatBytes(tx[h],2))
        print(msg)
        sendtweet(t, msg)
    msg = "Insgesamt wurden gestern %s übertragen, davon wurden %s heruntergeladen und %s hochgeladen." % \
        (formatBytes(allrx + alltx,2), formatBytes(allrx,2), formatBytes(alltx,2))
    print(msg)
    sendtweet(t, msg)
