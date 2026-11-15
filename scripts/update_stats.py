"""Refresh public profile statistics without third-party dependencies."""

import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OWNER = "altsun"
README = Path(__file__).resolve().parents[1] / "README.md"
START, END = "<!-- STATS:START -->", "<!-- STATS:END -->"
QUERY = "repo:freeCodeCamp/freeCodeCamp is:pr is:merged author:altsun"


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
        lines += ["| Language | Code share |", "| --- | ---: |"]
        for language, size in sorted(languages.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| {language} | {size / total * 100:.1f}% |")
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
    if updated != original:
        temporary = README.with_suffix(".md.tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(README)


if __name__ == "__main__":
    main()
