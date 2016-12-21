#!/usr/bin/env python3
from base import *
import time
from helpers import getelem,floatdef,haversine
from math import log2
import sys

if mongodb["templates"].count() == 0:
    mongodb["templates"].insert([
        {"type":"noderip",          "msg":"Node rip {hostname}"},
        {"type":"nodeonline",       "msg":"Node online {hostname}"},
        {"type":"nodenew",          "msg":"New node {hostname}"},
        {"type":"nodenewfirmware",  "msg":"New firmware {hostname}: ({new})"},
        {"type":"nodenewmail",      "msg":"New mail {hostname}: ({new})"},
        {"type":"nodenewposition",  "msg":"New position {hostname}: {new[0]} ; {new[1]} ({dist}m)"},
        {"type":"nodelate",         "msg":"Node late {hostname}"},
        {"type":"nodeoffline",      "msg":"Node offline {hostname}"},
        {"type":"linknew",          "msg":"New Link {ha} <-> {hb} ({ipa} : {ipb}) ETX: {newetx3}"},
        {"type":"linkest",          "msg":"Established Link {ha} <-> {hb} ({ipa} : {ipb}) ETX: {oldetx3} -> {newetx3}"},
        {"type":"linkbroken",       "msg":"Broken Link {ha} <-> {hb} ({ipa} : {ipb}) ETX: {oldetx3} -> {newetx3}"},
        {"type":"linkbetter",       "msg":"Better link {ha} <-> {hb} ({ipa} : {ipb}) ETX: {oldetx3} -> {newetx3}"},
        {"type":"linkworse",        "msg":"Worse link {ha} <-> {hb} ({ipa} : {ipb}) ETX: {oldetx3} -> {newetx3}"},
    ])

if len(sys.argv) == 1 or sys.argv[1] != "--np":
    donelinks = []
    for lp in mongodb["linkperf"].find(sort=[("time",-1)]):
        for l in lp["l"]:
            lid = "_".join(sorted([l["a"]["ip"],l["b"]["ip"]]))
            if lid not in donelinks:
                if "etx3" in l and "etx24" in l:
                    donelinks.append(lid)
                    doc = {
                        "linkid":lid,
                        "time":time.time(),
                        "etx3":l["etx3"],
                        "etx24":l["etx24"],
                        "ha":lp["ha"],
                        "hb":lp["hb"],
                        "ipa":l["a"]["ip"],
                        "ipb":l["b"]["ip"],
                    }
                    mongodb["histlinks"].insert(doc)
    for n in mongodb["nodes"].find():
        doc = {
            "hostname":n["hostname"],
            "time":time.time()
        }
        doc["delay"] = doc["time"] - n["last_ts"]
        doc["firmware"] = getelem(n,"sysinfo.firmware","")
        doc["mail"] = getelem(n,"sysinfo.mail","")
        doc["lon"] = floatdef(getelem(n,"sysinfo.longitude",0),0)
        doc["lat"] = floatdef(getelem(n,"sysinfo.latitude",0),0)
        doc["neighbors"] = {}
        for l in mongodb["linkperf"].find({"etx":{"$lt":10},"$or":[{"ha":n["hostname"]},{"hb":n["hostname"]}]}):
            if l["ha"] != l["hb"]:
                name = l["ha"] if l["ha"] != n["hostname"] else l["hb"]
                doc["neighbors"][name] = l["etx24"]
        mongodb["histnodes"].insert(doc)
evts = []
for hostname in mongodb["histnodes"].distinct("hostname"):
    hist = list(mongodb["histnodes"].find({"hostname":hostname,"time":{"$gt":time.time() - 24*3600}}, sort=[("time",-1)]))
    if mongodb["nodes"].find_one({"hostname":hostname}) is None:
        evts.append({
            "type":"noderip",
            "hostname":hist[0]["hostname"],
        })
        mongodb["histnodes"].remove({"hostname":hostname})
    elif len(hist) == 1:
        evts.append({
            "type":"nodenew",
            "hostname":hist[0]["hostname"],
        })
    elif len(hist) > 1:
        if hist[0]["firmware"] != hist[1]["firmware"] and hist[1]["firmware"] != "":
            evts.append({
                "type":"nodenewfirmware",
                "hostname":hist[0]["hostname"],
                "new":hist[0]["firmware"],
                "old":hist[1]["firmware"],
            })
        if hist[0]["mail"] != hist[1]["mail"] and hist[1]["mail"] != "":
            evts.append({
                "type":"nodenewmail",
                "hostname":hist[0]["hostname"],
                "new":hist[0]["mail"],
                "old":hist[1]["mail"],
            })
        dist = 1000 * haversine(hist[0]["lon"],hist[0]["lat"],hist[1]["lon"],hist[1]["lat"])
        if dist > 10 and haversine(0,0,hist[1]["lon"],hist[1]["lat"]) > 10:
            evts.append({
                "type":"nodenewposition",
                "hostname":hist[0]["hostname"],
                "new":[hist[0]["lon"],hist[0]["lat"]],
                "old":[hist[1]["lon"],hist[1]["lat"]],
                "dist":dist,
            })
        if hist[0]["delay"] > 3 * 3600 and hist[1]["delay"] <= 3 * 3600:
            evts.append({
                "type":"nodelate",
                "hostname":hist[0]["hostname"],
            })
        elif hist[0]["delay"] > 24 * 3600 and hist[1]["delay"] <= 24 * 3600:
            evts.append({
                "type":"nodeoffline",
                "hostname":hist[0]["hostname"],
            })
        elif hist[0]["delay"] < 3 * 3600 and hist[1]["delay"] >= 3 * 3600:
            evts.append({
                "type":"nodeonline",
                "hostname":hist[0]["hostname"],
            })
if False:
    for lid in mongodb["histlinks"].distinct("linkid"):
        hist = list(mongodb["histlinks"].find({"linkid":lid,"time":{"$gt":time.time()-24*3600}}, sort=[("time",-1)]))
        if len(hist) == 1 and hist[0]["etx3"] < 10:
            evts.append({
                "type":"linknew",
                "ha":hist[0]["ha"],
                "hb":hist[0]["hb"],
                "ipa":hist[0]["ipa"],
                "ipb":hist[0]["ipb"],
                "newetx3":hist[0]["etx3"],
                "newetx24":hist[0]["etx24"],
            })
        elif len(hist) > 1:
            fact = []
            if hist[0]["etx24"] < 10 and abs(log2(hist[0]["etx3"]) - log2(hist[1]["etx3"])) > 1:
                evttype = None
                if hist[0]["etx3"] < 10 and hist[1]["etx3"] > 20:
                    evttype = "linkest"
                elif hist[0]["etx3"] > 20 and hist[1]["etx3"] < 10:
                    evttype = "linkbroken"
                elif hist[0]["etx3"] > 10 and hist[1]["etx3"] > 10:
                    evttype = None
                elif hist[0]["etx3"] < hist[1]["etx3"]:
                    evttype = "linkbetter"
                elif hist[0]["etx3"] > hist[1]["etx3"]:
                    evttype = "linkworse"
                if evttype is not None:
                    evts.append({
                        "type":evttype,
                        "ha":hist[0]["ha"],
                        "hb":hist[0]["hb"],
                        "ipa":hist[0]["ipa"],
                        "ipb":hist[0]["ipb"],
                        "newetx3":hist[0]["etx3"],
                        "newetx24":hist[0]["etx24"],
                        "oldetx3":hist[1]["etx3"],
                        "oldetx24":hist[1]["etx24"],
                    })
t = time.time()
for e in evts:
    e["time"] = t
    mongodb["events"].insert(e)
    t += 900 / len(evts)

mongodb["histnodes"].remove({"time":{"$lt":time.time() - 14*24*3600}})
mongodb["histlinks"].remove({"time":{"$lt":time.time() - 14*24*3600}})
