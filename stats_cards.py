"""Generate on-brand GitHub stats cards as static SVGs.

Runs in GitHub Actions with GITHUB_TOKEN. No third-party dependencies.
Writes assets/stats.svg and assets/langs.svg.
"""
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = os.environ.get("GH_USER", "ayush-jha-ai")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path(__file__).resolve().parent.parent / "assets"

BG, ACCENT, TEXT, MUTED = "#1F0F53", "#FFDB99", "#FFFFFF", "#B9B0D9"
FONT = "'JetBrains Mono','SFMono-Regular',Consolas,monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
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


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": USER},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def summarise(u):
    cc = u["contributionsCollection"]
    repos = u["repositories"]
    langs = {}
    for repo in repos["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            colour = e["node"]["color"] or MUTED
            size, _ = langs.get(name, (0, colour))
            langs[name] = (size + e["size"], colour)
    return {
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": cc["totalPullRequestContributions"],
        "repos": repos["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos["nodes"]),
        "followers": u["followers"]["totalCount"],
        "langs": sorted(langs.items(), key=lambda kv: kv[1][0], reverse=True)[:6],
    }


def frame(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{ACCENT}" stroke-opacity="0.35"/>
  <text x="24" y="36" font-size="14" font-weight="700" fill="{ACCENT}">{escape(title)}</text>
  <line x1="24" y1="48" x2="{w-24}" y2="48" stroke="{ACCENT}" stroke-opacity="0.25" stroke-dasharray="4 4"/>
{body}
</svg>
"""


def stats_svg(s):
    rows = [
        ("Commits this year", s["commits"], "M1"),
        ("Pull requests this year", s["prs"], "M1"),
        ("Public repos", s["repos"], "A1"),
        ("Stars earned", s["stars"], "A1"),
        ("Followers", s["followers"], "B1"),
    ]
    body = ""
    for i, (label, val, mark) in enumerate(rows):
        y = 78 + i * 22
        body += (
            f'  <text x="24" y="{y}" font-size="12" fill="{TEXT}">{label}</text>\n'
            f'  <text x="300" y="{y}" font-size="12" font-weight="700" fill="{TEXT}" text-anchor="end">{val}</text>\n'
            f'  <text x="326" y="{y}" font-size="11" fill="{ACCENT}" text-anchor="end">{mark}</text>\n'
        )
    return frame(350, 180, "Q5 · Activity  [marks awarded]", body)


def langs_svg(s):
    langs = s["langs"]
    total = sum(v[0] for _, v in langs) or 1
    w, bar_w = 350, 302
    body, x = "", 24
    for name, (size, colour) in langs:
        seg = bar_w * size / total
        body += f'  <rect x="{x:.1f}" y="64" width="{seg:.1f}" height="8" fill="{colour}"/>\n'
        x += seg
    for i, (name, (size, colour)) in enumerate(langs):
        col, row = i % 2, i // 2
        cx, cy = 24 + col * 160, 98 + row * 24
        body += (
            f'  <circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{colour}"/>\n'
            f'  <text x="{cx+16}" y="{cy}" font-size="12" fill="{TEXT}">{escape(name)} '
            f'<tspan fill="{MUTED}">{100*size/total:.1f}%</tspan></text>\n'
        )
    if not langs:
        body = f'  <text x="24" y="80" font-size="12" fill="{MUTED}">No public code yet.</text>\n'
    return frame(w, 180, "Q6 · Languages  [by bytes]", body)


def main():
    s = summarise(fetch()) if TOKEN else json.loads(os.environ["FAKE_STATS"])
    OUT.mkdir(exist_ok=True)
    (OUT / "stats.svg").write_text(stats_svg(s))
    (OUT / "langs.svg").write_text(langs_svg(s))
    print("Wrote", OUT / "stats.svg", OUT / "langs.svg")


if __name__ == "__main__":
    main()
