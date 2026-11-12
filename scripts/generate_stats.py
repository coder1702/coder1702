#!/usr/bin/env python3
"""Generate assets/stats.svg (terminal-style GitHub stats card).

Runs inside GitHub Actions using the built-in GITHUB_TOKEN. Standard library only.
Without a token it writes a placeholder card, so the README image never breaks.
"""
import datetime
import html
import json
import os
import urllib.request

USER = os.environ.get("GH_USER", "coder1702")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = os.environ.get("STATS_OUT", "assets/stats.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection { contributionCalendar { totalContributions } }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# palette: bg #0D1117 | panel #161B22 | border #30363D | blue #58A6FF | purple #8957E5 | text #C9D1D9 | muted #8B949E
FALLBACK_COLOR = "#8B949E"


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-card",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    user = data["data"]["user"]
    repos = user["repositories"]["nodes"]
    langs = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = langs.setdefault(name, {"size": 0, "color": edge["node"]["color"] or FALLBACK_COLOR})
            entry["size"] += edge["size"]
    return {
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": user["followers"]["totalCount"],
        "contribs": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "langs": langs,
    }


def render(stats):
    live = stats is not None
    v = (lambda k: f"{stats[k]:,}") if live else (lambda k: "–")

    # languages: top 5 by size, as % of the shown total
    segs, legend = "", ""
    if live and stats["langs"]:
        top = sorted(stats["langs"].items(), key=lambda kv: kv[1]["size"], reverse=True)[:5]
        total = sum(d["size"] for _, d in top) or 1
        x, bar_w = 470, 390
        for i, (name, d) in enumerate(top):
            pct = d["size"] / total * 100
            w = bar_w * d["size"] / total
            segs += f'<rect x="{x:.1f}" y="112" width="{max(w - 2, 1):.1f}" height="12" rx="3" fill="{html.escape(d["color"])}"/>'
            x += w
            y = 158 + i * 26
            legend += (
                f'<circle cx="476" cy="{y - 5}" r="5" fill="{html.escape(d["color"])}"/>'
                f'<text x="492" y="{y}" font-size="15" fill="#C9D1D9">{html.escape(name)}</text>'
                f'<text x="860" y="{y}" font-size="15" fill="#8B949E" text-anchor="end">{pct:.1f}%</text>'
            )
    else:
        legend = '<text x="470" y="150" font-size="14" fill="#8B949E">waiting for the first workflow run</text>'

    stamp = datetime.date.today().isoformat() if live else "not generated yet"
    rows = [("repos", v("repos")), ("stars", v("stars")), ("followers", v("followers")), ("contributions", v("contribs"))]
    row_svg = ""
    for i, (label, value) in enumerate(rows):
        y = 158 + i * 26
        row_svg += (
            f'<text x="44" y="{y}" font-size="16" fill="#8B949E">{label}</text>'
            f'<text x="290" y="{y}" font-size="18" font-weight="700" fill="#58A6FF" text-anchor="end">{value}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 300" width="900" height="300" role="img" aria-labelledby="t">
  <title id="t">GitHub stats for {html.escape(USER)}</title>
  <style>text {{ font-family: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace; }}</style>
  <rect width="900" height="300" rx="12" fill="#0D1117"/>
  <rect x="1" y="1" width="898" height="298" rx="12" fill="#161B22" stroke="#30363D"/>
  <path d="M1 13a12 12 0 0 1 12-12h874a12 12 0 0 1 12 12v31H1z" fill="#1C2128"/>
  <line x1="1" y1="44" x2="899" y2="44" stroke="#30363D"/>
  <circle cx="28" cy="23" r="6" fill="#FF5F56"/><circle cx="50" cy="23" r="6" fill="#FFBD2E"/><circle cx="72" cy="23" r="6" fill="#27C93F"/>
  <text x="450" y="28" font-size="13" fill="#8B949E" text-anchor="middle">kalp@shah: ~/stats</text>

  <text x="44" y="84" font-size="17"><tspan fill="#3FB950">$</tspan><tspan fill="#C9D1D9"> gh stats</tspan></text>
  {row_svg}
  <text x="184" y="236" font-size="11" fill="#484F58">last year</text>

  <line x1="420" y1="64" x2="420" y2="268" stroke="#21262D"/>

  <text x="470" y="84" font-size="17"><tspan fill="#3FB950">$</tspan><tspan fill="#C9D1D9"> top --langs</tspan></text>
  {segs}
  {legend}

  <text x="860" y="289" font-size="11" fill="#484F58" text-anchor="end">updated {stamp}</text>
</svg>
'''


def main():
    stats = None
    if TOKEN:
        try:
            stats = fetch()
        except Exception as exc:  # keep the previous card if the API hiccups
            print(f"GitHub API failed: {exc}")
            if os.path.exists(OUT):
                return
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(render(stats))
    print(f"wrote {OUT} ({'live' if stats else 'placeholder'})")


if __name__ == "__main__":
    main()
