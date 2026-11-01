#!/usr/bin/env python3
"""One-time helper to obtain a Spotify refresh token for the worker.

    .venv/bin/python tools/spotify_auth.py

You'll be asked for the client id/secret, given a URL to open, and asked to
paste back the ?code= parameter of the redirect. Prints a refresh token to
store as the worker's SPOTIFY_REFRESH_TOKEN secret. The redirect URI is fixed
to http://127.0.0.1:8765/callback and must exactly match the Spotify app.
"""

import base64
import http.server
import json
import urllib.parse
import urllib.request

REDIRECT_PORT = 8765
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"


def main() -> None:
    client_id = input("SPOTIFY_CLIENT_ID: ").strip()
    client_secret = input("SPOTIFY_CLIENT_SECRET: ").strip()

    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": "user-read-currently-playing user-read-recently-played",
        }
    )
    print("\nOpen this URL, approve access, and you'll be redirected here:\n")
    print(auth_url)

    holder: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (stdlib API)
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            holder["code"] = (qs.get("code") or [""])[0]
            holder["error"] = (qs.get("error") or [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write("got it — you can close this tab".encode())

        def log_message(self, *args):  # silence
            pass

    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler)
    print(f"\nlistening on {REDIRECT_URI} ...\n")
    server.handle_request()
    server.server_close()

    if holder.get("error") or not holder.get("code"):
        raise SystemExit(f"authorization failed: {holder.get('error') or 'no code returned'}")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": holder["code"],
                "redirect_uri": REDIRECT_URI,
            }
        ).encode(),
        headers={"Authorization": f"Basic {basic}"},
    )
    data = json.load(urllib.request.urlopen(req))
    print("\nSPOTIFY_REFRESH_TOKEN:\n")
    print(data["refresh_token"])
    print("\nStore it:  npx wrangler secret put SPOTIFY_REFRESH_TOKEN")


if __name__ == "__main__":
    main()
