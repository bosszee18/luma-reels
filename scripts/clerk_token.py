import os, sys, json, urllib.request, urllib.parse
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
SK = os.environ["CLERK_SECRET_KEY"]


def bapi(path, body=None, method="POST"):
    req = urllib.request.Request("https://api.clerk.com/v1" + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers={"Authorization": "Bearer " + SK, "Content-Type": "application/json",
                                                         "User-Agent": "emergent-test"})
    return json.load(urllib.request.urlopen(req))


email = sys.argv[1] if len(sys.argv) > 1 else "kreator+clerk_test@example.com"
mode = sys.argv[2] if len(sys.argv) > 2 else "token"
found = bapi("/users?" + urllib.parse.urlencode({"email_address": email}), method="GET")
user = found[0] if found else bapi("/users", {"email_address": [email], "password": "Luma-Test-2026!", "skip_password_checks": True})
if mode == "ticket":
    print(bapi("/sign_in_tokens", {"user_id": user["id"], "expires_in_seconds": 3600})["token"])
else:
    s = bapi("/sessions", {"user_id": user["id"]})
    print(bapi(f"/sessions/{s['id']}/tokens", {"expires_in_seconds": 3600})["jwt"])
