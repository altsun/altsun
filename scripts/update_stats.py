"""Refresh public profile statistics without third-party dependencies."""

import json
import os
from html import escape
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OWNER = "altsun"
README = Path(__file__).resolve().parents[1] / "README.md"
START, END = "<!-- STATS:START -->", "<!-- STATS:END -->"
QUERY = "repo:freeCodeCamp/freeCodeCamp is:pr is:merged author:altsun"
CHART = README.parent / "assets/languages.svg"
COLORS = {"Common Lisp": "#3fb68b", "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c", "Less": "#1d365d", "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572a5", "Clean": "#3f85af", "Procfile": "#945db7"}


def chart(languages):
    ordered = sorted(languages.items(), key=lambda item: (-item[1], item[0]))
    total = sum(languages.values())
    height = 64 + 28 * len(ordered)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{height}" viewBox="0 0 640 {height}" role="img" aria-labelledby="title desc">',
             '<title id="title">Public repository language shares</title>',
             '<desc id="desc">' + escape(', '.join(f'{name}: {size / total * 100:.1f}%' for name, size in ordered)) + '</desc>',
             f'<rect width="640" height="{height}" rx="12" fill="#0d1117"/>']
    x = 20
    for index, (name, size) in enumerate(ordered):
        color = COLORS.get(name, ("#a78bfa", "#fb923c", "#38bdf8")[index % 3])
        width = size / total * 600
        y = 66 + index * 28
        parts += [f'<rect x="{x:.4f}" y="20" width="{width:.4f}" height="18" fill="{color}"/>',
                  f'<circle cx="26" cy="{y - 5}" r="5" fill="{color}"/>',
                  f'<text x="42" y="{y}" fill="#e6edf3" font-family="Arial, sans-serif" font-size="14">{escape(name)}</text>',
                  f'<text x="620" y="{y}" text-anchor="end" fill="#e6edf3" font-family="Arial, sans-serif" font-size="14">{size / total * 100:.1f}%</text>']
        x += width
    return '\n'.join(parts + ['</svg>']) + '\n'


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "altsun-profile"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/{path}", headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def collect(fetch=api):
    languages = Counter()
    page = 1
    while True:
        repos = fetch(f"users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        for repo in repos:
            if repo["fork"] or repo["archived"] or repo.get("private") or repo["name"].lower() == OWNER:
                continue
            languages.update(fetch(f"repos/{OWNER}/{repo['name']}/languages"))
        if len(repos) < 100:
            break
        page += 1
    result = fetch("search/issues?" + urlencode({"q": QUERY, "per_page": 1}))
    if result.get("incomplete_results", True):
        raise RuntimeError("GitHub returned incomplete PR search results")
    return languages, result["total_count"]


def render(languages, merged):
    link = "https://github.com/freeCodeCamp/freeCodeCamp/pulls?" + urlencode({"q": "is:pr is:merged author:altsun"})
    lines = ["## 🤝 Open Source Contributions", "",
             f"[**freeCodeCamp/freeCodeCamp — {merged} merged pull requests**]({link})", "",
             "## 📊 Languages across my public repositories", ""]
    total = sum(languages.values())
    if total:
        description = ", ".join(f"{name}: {size / total * 100:.1f}%" for name, size in sorted(languages.items(), key=lambda item: (-item[1], item[0])))
        lines.append(f"![Language shares — {description}](assets/languages.svg)")
    else:
        lines.append("No language data available yet.")
    lines += ["", "Based on source-code bytes reported by GitHub, not proficiency. Forks, archived repositories and this profile repository are excluded. GitHub may classify AutoLISP as Common Lisp. Percentages may not total 100% due to rounding.", "",
              "Updated weekly on Mondays at 07:00 Vietnam time. PR counts may lag behind GitHub's search index."]
    return "\n".join(lines)


def replace_stats(text, body):
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("Expected exactly one statistics marker pair")
    before, rest = text.split(START)
    _, after = rest.split(END)
    return before + START + "\n" + body + "\n" + END + after


def main():
    original = README.read_text(encoding="utf-8")
    languages, merged = collect()
    updated = replace_stats(original, render(languages, merged))
    if sum(languages.values()):
        CHART.parent.mkdir(parents=True, exist_ok=True)
        CHART.write_text(chart(languages), encoding="utf-8")
    if updated != original:
        temporary = README.with_suffix(".md.tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(README)


if __name__ == "__main__":
    main()
