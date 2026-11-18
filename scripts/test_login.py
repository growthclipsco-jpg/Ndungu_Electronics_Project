"""Quick login test script."""
import urllib.request, urllib.parse, re, http.cookiejar

base = "http://127.0.0.1:5000"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# GET login page
resp = opener.open(base + "/login")
html = resp.read().decode("utf-8")

m = re.search(r'name="csrf_token" value="([^"]+)"', html)
csrf = m.group(1) if m else ""
print("CSRF token found:", bool(csrf), "|", csrf[:30] if csrf else "MISSING")

# POST login
data = urllib.parse.urlencode({
    "username": "Augustin Sanga",
    "password": "200 Sanga",
    "csrf_token": csrf,
}).encode()

req = urllib.request.Request(base + "/login", data=data, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    resp2 = opener.open(req)
    print("POST status:", resp2.status)
    print("Final URL:", resp2.url)
    body = resp2.read().decode("utf-8")
    if "inventory" in body.lower() or "dashboard" in body.lower():
        print("SUCCESS - landed on inventory/dashboard page")
    elif "invalid" in body.lower() or "error" in body.lower():
        m2 = re.search(r'<[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)<', body)
        print("FAILED - error:", m2.group(1) if m2 else "unknown error")
        # Print flash messages area
        for line in body.split("\n"):
            if "error" in line.lower() or "invalid" in line.lower() or "locked" in line.lower():
                print(" >>", line.strip()[:120])
    else:
        print("Unknown response - first 300 chars:")
        print(body[:300])
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.reason)
    body = e.read().decode("utf-8")
    print(body[:500])
