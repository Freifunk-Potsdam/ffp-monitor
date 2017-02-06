#!/usr/bin/env python3
from base import *
import time
from twitter import *
import traceback
import random
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
#            print(msg)
            mongodb["tweets"].insert({ "msg": msg, "sent": now, "ctime": c["time"] })
            break
