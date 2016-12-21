#!/usr/bin/env python3
from base import *
import time
import random
random.seed()

for e in mongodb["events"].find({"time":{"$lte":time.time()},"sent":{"$exists":False}}):
    tpls = list(mongodb["templates"].find({"type":e["type"]}))
    if len(tpls) > 0:
        msg = random.choice(tpls)["msg"].format_map(e)
        print(msg)
        mongodb["events"].update({"_id":e["_id"]},{"$set":{"sent":time.time()}})
    else:
        print("No template of type %s found." % e["type"])
