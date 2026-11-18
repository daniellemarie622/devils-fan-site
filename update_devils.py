import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

TEAM = "NJD"
API = "https://api-web.nhle.com/v1"
NEWS_URL = "https://www.nhl.com/devils/news/"
TRANSACTIONS_URL = "https://www.nhl.com/devils/news/topic/transactions/"
INJURIES_URL = "https://www.nhl.com/devils/news/topic/injury-reports/"
OUTPUT_DIR = "data"
PREVIOUS_FILE = os.path.join(OUTPUT_DIR, "roster-previous.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "devils.json")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; DevilsFanSiteUpdater/1.0)",
    "Accept": "application/json,text/html,application/xhtml+xml"
})


def fetch_json(url):
    response = SESSION.get(url, timeout=25)
    response.raise_for_status()
    return response.json()


def text_value(value):
    if isinstance(value, dict):
        return value.get("default") or next(iter(value.values()), "")
    return value or ""


def get_player_stats(player_id):
    try:
        data = fetch_json(f"{API}/player/{player_id}/landing")
        featured = data.get("featuredStats", {}).get("regularSeason", {})
        stats = featured.get("subSeason", {}) or {}
        return stats
    except Exception as error:
        print(f"Could not retrieve stats for player {player_id}: {error}")
        return {}


def parse_articles(url, limit=15):
    try:
        response = SESSION.get(url, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        articles = []
        seen = set()

        for anchor in soup.select('a[href*="/devils/news/"]'):
            href = anchor.get("href", "")
            title = " ".join(anchor.get_text(" ", strip=True).split())

            if not title or len(title) < 8:
                continue

            full_url = urljoin("https://www.nhl.com", href)

            if full_url in seen:
                continue
            if "/news/topic/" in full_url and full_url.rstrip("/").endswith("/news/topic"):
                continue

            seen.add(full_url)
            parent_text = " ".join(anchor.parent.get_text(" ", strip=True).split()) if anchor.parent else ""
            date_match = re.search(
                r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2}\b",
                parent_text,
                re.IGNORECASE
            )

            articles.append({
                "title": title,
                "url": full_url,
                "date": date_match.group(0) if date_match else ""
            })

            if len(articles) >= limit:
                break

        return articles
    except Exception as error:
        print(f"Could not retrieve articles from {url}: {error}")
        return []


def load_previous():
    if not os.path.exists(PREVIOUS_FILE):
        return None
    try:
        with open(PREVIOUS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


def save_json(path, value):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(value, file, indent=2, ensure_ascii=False)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    roster_data = fetch_json(f"{API}/roster/{TEAM}/current")
    standings_data = fetch_json(f"{API}/standings/now")

    team_standing = {}
    for item in standings_data.get("standings", []):
        if text_value(item.get("teamAbbrev")) == TEAM:
            team_standing = item
            break

    standings = {
        "wins": team_standing.get("wins"),
        "losses": team_standing.get("losses"),
        "overtimeLosses": team_standing.get("otLosses"),
        "points": team_standing.get("points"),
        "gamesPlayed": team_standing.get("gamesPlayed"),
        "division": text_value(team_standing.get("divisionName")),
        "divisionRank": team_standing.get("divisionSequence"),
        "goalsFor": team_standing.get("goalFor"),
        "goalsAgainst": team_standing.get("goalAgainst")
    }

    roster_groups = [
        ("forwards", roster_data.get("forwards", [])),
        ("defensemen", roster_data.get("defensemen", [])),
        ("goalies", roster_data.get("goalies", []))
    ]

    players = []
    for group_name, group in roster_groups:
        for player in group:
            first = text_value(player.get("firstName"))
            last = text_value(player.get("lastName"))
            players.append({
                "id": player.get("id"),
                "number": player.get("sweaterNumber"),
                "name": (first + " " + last).strip(),
                "position": player.get("positionCode", ""),
                "group": group_name
            })

    stats_by_id = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(get_player_stats, player["id"]): player["id"]
            for player in players if player.get("id")
        }
        for future in as_completed(futures):
            stats_by_id[futures[future]] = future.result()

    skaters = []
    goalies = []

    for player in players:
        stats = stats_by_id.get(player["id"], {})
        if player["group"] == "goalies":
            goalies.append({
                **player,
                "games": stats.get("games"),
                "wins": stats.get("wins"),
                "losses": stats.get("losses"),
                "overtimeLosses": stats.get("otLosses"),
                "goalsAgainstAverage": stats.get("goalsAgainstAvg"),
                "savePercentage": (
                    f'{stats["savePctg"]:.3f}'
                    if isinstance(stats.get("savePctg"), (int, float))
                    else stats.get("savePctg")
                ),
                "shutouts": stats.get("shutouts")
            })
        else:
            skaters.append({
                **player,
                "games": stats.get("games"),
                "goals": stats.get("goals"),
                "assists": stats.get("assists"),
                "points": stats.get("points"),
                "plusMinus": stats.get("plusMinus"),
                "pim": stats.get("pim"),
                "timeOnIce": stats.get("avgToi")
            })

    skaters.sort(
        key=lambda player: (
            player.get("points") is not None,
            player.get("points") or 0
        ),
        reverse=True
    )

    news = parse_articles(NEWS_URL, 15)
    transactions = parse_articles(TRANSACTIONS_URL, 20)
    injury_reports = parse_articles(INJURIES_URL, 15)

    # Keep only headlines that look like actual roster moves.
    move_terms = (
        "recall", "recalled", "loan", "loaned", "assign", "assigned",
        "waiver", "waived", "injured reserve", "placed on ir",
        "placed on ltir", "activated", "acquired", "trade"
    )
    transactions = [
        article for article in transactions
        if any(term in article["title"].lower() for term in move_terms)
    ]

    # Use official injury-report articles rather than guessing a player's
    # current status from an old roster snapshot or an unrelated headline.
    injury_terms = (
        "injury", "injured", "surgery", "out ", "return", "medical",
        "illness", "fracture", "sprain", "status"
    )
    injury_reports = [
        article for article in injury_reports
        if any(term in article["title"].lower() for term in injury_terms)
    ]

    practice_terms = ("notebook", "practice", "morning skate", "line")
    practice_notes = [
        article for article in news
        if any(term in article["title"].lower() for term in practice_terms)
    ][:5]

    previous = load_previous()
    current_by_id = {
        str(player["id"]): {
            "id": player["id"],
            "number": player.get("number"),
            "name": player.get("name"),
            "position": player.get("position")
        }
        for player in players if player.get("id") is not None
    }

    baseline_exists = previous is not None
    if previous is None:
        previous = {}

    previous_ids = set(previous.keys())
    current_ids = set(current_by_id.keys())

    roster_changes = {
        "baselineExists": baseline_exists,
        "newlyListed": [
            current_by_id[player_id]
            for player_id in sorted(current_ids - previous_ids)
        ] if baseline_exists else [],
        "noLongerListed": [
            previous[player_id]
            for player_id in sorted(previous_ids - current_ids)
        ] if baseline_exists else []
    }

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "team": "New Jersey Devils",
        "season": "2026-27",
        "standings": standings,
        "skaters": skaters,
        "goalies": goalies,
        "news": news,
        "transactions": transactions,
        "injuryReports": injury_reports,
        "practiceNotes": practice_notes,
        "rosterChanges": roster_changes
    }

    save_json(OUTPUT_FILE, output)
    save_json(PREVIOUS_FILE, current_by_id)

    print(
        "Updated Devils data:",
        len(skaters), "skaters,",
        len(goalies), "goalies,",
        len(news), "news articles,",
        len(transactions), "transactions,",
        len(injury_reports), "injury reports."
    )


if __name__ == "__main__":
    main()
