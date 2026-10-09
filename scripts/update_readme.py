"""Refresh the auto-generated sections of README.md from the GitHub API.

Sections are delimited by marker comments, e.g.
    <!--REPOS:START--> ... <!--REPOS:END-->
Run locally:  GH_USER=sumairali01 python scripts/update_readme.py
"""
import json
import os
import re
import urllib.request
from collections import Counter
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "sumairali01")
TOKEN = os.environ.get("GITHUB_TOKEN")
README = os.environ.get("README_PATH", "README.md")


def api(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "readme-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def replace_section(text, name, content):
    pattern = re.compile(
        rf"(<!--{name}:START-->)(.*?)(<!--{name}:END-->)", re.DOTALL
    )
    if not pattern.search(text):
        print(f"warning: marker {name} not found")
        return text
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}"
                       if "\n" in content or name != "UPDATED"
                       else f"{m.group(1)}{content}{m.group(3)}", text)


def build_stats(profile, repos):
    langs = Counter(r["language"] for r in repos if r.get("language"))
    total = sum(langs.values()) or 1
    lines = [
        "| Public repos | Followers | Following |",
        "|:-:|:-:|:-:|",
        f"| {profile['public_repos']} | {profile['followers']} | {profile['following']} |",
        "",
        "**Language mix (by repository)**",
        "",
        "```text",
    ]
    for lang, count in langs.most_common(5):
        share = count / total
        bar = "█" * max(1, round(share * 20))
        lines.append(f"{lang:<12} {bar:<20} {share:>4.0%}")
    if not langs:
        lines.append("No language data yet.")
    lines.append("```")
    return "\n".join(lines)


def build_repos(repos):
    own = [
        r for r in repos
        if not r["fork"] and r["name"].lower() != USER.lower()
    ]
    own.sort(key=lambda r: r["pushed_at"], reverse=True)
    if not own:
        return "_No public repositories yet._"
    out = []
    for r in own[:5]:
        desc = (r.get("description") or "No description").replace("|", "/")
        meta = [r["language"]] if r.get("language") else []
        meta.append(f"★ {r['stargazers_count']}")
        meta.append(f"updated {r['pushed_at'][:10]}")
        out.append(
            f"- [**{r['name']}**]({r['html_url']}) — {desc}  \n"
            f"  <sub>{' · '.join(meta)}</sub>"
        )
    return "\n".join(out)


def build_activity(events):
    out = []
    for e in events:
        if e["type"] != "PushEvent":
            continue
        repo = e["repo"]["name"]
        if repo.split("/")[-1].lower() == USER.lower():
            continue  # ignore the profile repo's own bot commits
        n = e["payload"].get("size") or len(e["payload"].get("commits", [])) or 1
        word = "commit" if n == 1 else "commits"
        out.append(
            f"- `{e['created_at'][:10]}` pushed {n} {word} to "
            f"[{repo}](https://github.com/{repo})"
        )
        if len(out) == 5:
            break
    return "\n".join(out) if out else "_No recent public pushes._"


def main():
    profile = api(f"/users/{USER}")
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner&sort=pushed")
    events = api(f"/users/{USER}/events/public?per_page=50")

    with open(README, encoding="utf-8") as f:
        text = f.read()

    text = replace_section(text, "STATS", build_stats(profile, repos))
    text = replace_section(text, "REPOS", build_repos(repos))
    text = replace_section(text, "ACTIVITY", build_activity(events))
    # date only, so the bot commits at most once per day
    text = replace_section(
        text, "UPDATED", datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print("README updated")


if __name__ == "__main__":
    main()
