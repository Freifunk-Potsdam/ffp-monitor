#!/usr/bin/env python3
from base import *
import time
from twitter import *
import random
random.seed()

from twitter_auth import *

t = Twitter( auth = OAuth( access_token, access_token_secret, consumer_key, consumer_secret ))

for e in mongodb["events"].find({"time":{"$lte":time.time()},"sent":{"$exists":False}}):
    tpls = list(mongodb["templates"].find({"type":e["type"]}))
    if len(tpls) > 0:
        sent = False
        msg = random.choice(tpls)["msg"].format_map(e)
        if len(msg) > 140:
            msg = msg[:137] + "..."
        try:
            t.statuses.update( status = msg )
            sent = True
        except TwitterHTTPError as ex:
            errs = ex.response_data.get("errors",[])
            for err in errs:
                if err.get("code",0) == 187:
                    # duplicate, not sending again
                    sent = True
            if not sent:
                raise ex
        if sent:
            mongodb["events"].update({"_id":e["_id"]},{"$set":{"sent":time.time()}})
    else:
        print("No template of type %s found." % e["type"])
