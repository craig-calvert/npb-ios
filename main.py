import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Simple in-memory cache
_players_cache = None
_players_cache_time = None
CACHE_DURATION = timedelta(hours=6)


# ✅ Function defined FIRST
def get_standings(season: int = 2026) -> dict:
    try:
        url = f"https://npb.jp/bis/eng/{season}/standings/index.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        result = {}
        for table in soup.select("table.standings"):
            cl_header = table.find("td", class_="standingsHeadCl")
            pl_header = table.find("td", class_="standingsHeadPl")

            if cl_header:
                league = "Central League"
            elif pl_header:
                league = "Pacific League"
            else:
                continue

            teams = []
            for row in table.select("td.standingsTeam"):
                tr = row.parent
                cells = tr.find_all("td")
                teams.append(
                    {
                        "team": cells[0].text.strip(),
                        "games": int(cells[1].text.strip()),
                        "wins": int(cells[2].text.strip()),
                        "losses": int(cells[3].text.strip()),
                        "ties": int(cells[4].text.strip()),
                        "pct": cells[5].text.strip(),
                        "gb": cells[6].text.strip(),
                    }
                )
            result[league] = teams
        return result
    except Exception as e:
        print(f"Error getting standings for {season}: {e}")
        return {"Central League": [], "Pacific League": []}


def get_schedule(year: int, month: int) -> list:
    """Get schedule for a specific month (returns today's games from the main page)"""
    url = f"https://npb.jp/bis/eng/{year}/games/"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    results = []

    # Get the date from the page
    date_tag = soup.select_one("h4.the_game_on_day span")
    date_str = date_tag.text.strip() if date_tag else ""

    # Find all game units
    game_units = soup.select("div.game_result span.link_box div.unit")

    for game_unit in game_units:
        # Get team information
        team_left = game_unit.select_one("div.team_left")
        team_right = game_unit.select_one("div.team_right")
        round_info = game_unit.select_one("div.round")

        if not (team_left and team_right and round_info):
            continue

        # Extract team names
        home_team = team_left.select_one("div.team_name")
        away_team = team_right.select_one("div.team_name")

        if not (home_team and away_team):
            continue

        # Extract scores (may be empty for future games)
        home_score = team_left.select_one("div.score_text")
        away_score = team_right.select_one("div.score_text")

        # Extract venue and time from round div
        round_text = round_info.get_text(separator="|", strip=True)
        round_parts = round_text.split("|")
        venue = round_parts[0] if len(round_parts) > 0 else ""
        game_time = round_parts[1] if len(round_parts) > 1 else ""

        # Try to extract game ID from link if available
        game_id = ""
        link_box = game_unit.find_parent("span", class_="link_box")
        if link_box and link_box.name == "a":
            href = link_box.get("href", "")
            if href:
                game_id = href.split("/")[-1].replace(".html", "")

        results.append(
            {
                "date": date_str,
                "home_team": home_team.text.strip(),
                "away_team": away_team.text.strip(),
                "home_runs": home_score.text.strip() if home_score else "",
                "away_runs": away_score.text.strip() if away_score else "",
                "venue": venue,
                "game_time": game_time,
                "game_id": game_id,
            }
        )

    return results


def get_schedule_by_date(year: int, month: int, day: int) -> list:
    try:
        url = f"https://npb.jp/bis/eng/{year}/games/gm{year}{month:02d}{day:02d}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        results = []

        # Date
        date_tag = soup.select_one("h4.the_game_on_day span")
        date_str = (
            date_tag.text.strip() if date_tag else f"{year}-{month:02d}-{day:02d}"
        )

        # Each game is an a.link_box
        for game_link in soup.select("a.link_box"):
            href = game_link.get("href", "")
            game_id = href.split("/")[-1].replace(".html", "") if href else ""

            home_team = ""
            away_team = ""
            home_runs = ""
            away_runs = ""
            venue = ""
            game_number = ""

            team_left = game_link.select_one("div.team_left div.team_name")
            team_right = game_link.select_one("div.team_right div.team_name")
            score_left = game_link.select_one("div.score_text.score_left")
            score_right = game_link.select_one("div.score_text.score_right")
            round_div = game_link.select_one("div.round")

            home_team = team_left.text.strip() if team_left else ""
            away_team = team_right.text.strip() if team_right else ""
            home_runs = score_left.text.strip() if score_left else ""
            away_runs = score_right.text.strip() if score_right else ""

            if round_div:
                round_parts = round_div.get_text(separator="\n").strip().split("\n")
                game_number = round_parts[0].strip() if round_parts else ""
                venue = round_parts[1].strip() if len(round_parts) > 1 else ""

            results.append(
                {
                    "date": date_str,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_runs": home_runs,
                    "away_runs": away_runs,
                    "venue": venue,
                    "game_number": game_number,
                    "game_id": game_id,
                }
            )

        return results
    except Exception as e:
        print(f"Error getting schedule for {year}/{month}/{day}: {e}")
        return []


def get_batting_stats(season: int, team_code: str) -> dict:
    try:
        url = f"https://npb.jp/bis/eng/{season}/stats/idb1_{team_code}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        # Get team name and league from title
        title_div = soup.select_one("div#stdivtitle h1")
        team_name = ""
        if title_div:
            team_name = title_div.text.strip().replace("\n", "").strip()

        league_tag = soup.select_one("div#stdivtitle h2")
        league = league_tag.text.strip() if league_tag else ""

        players = []
        for row in soup.select("tr.ststats"):
            cells = row.find_all("td")
            if len(cells) < 23:
                continue

            name = cells[1].text.strip()
            if not name:
                continue

            players.append(
                {
                    "name": name,
                    "games": cells[2].text.strip(),
                    "pa": cells[3].text.strip(),
                    "ab": cells[4].text.strip(),
                    "runs": cells[5].text.strip(),
                    "hits": cells[6].text.strip(),
                    "doubles": cells[7].text.strip(),
                    "triples": cells[8].text.strip(),
                    "hr": cells[9].text.strip(),
                    "tb": cells[10].text.strip(),
                    "rbi": cells[11].text.strip(),
                    "sb": cells[12].text.strip(),
                    "cs": cells[13].text.strip(),
                    "sh": cells[14].text.strip(),
                    "sf": cells[15].text.strip(),
                    "bb": cells[16].text.strip(),
                    "ibb": cells[17].text.strip(),
                    "hp": cells[18].text.strip(),
                    "so": cells[19].text.strip(),
                    "gdp": cells[20].text.strip(),
                    "avg": cells[21].text.strip(),
                    "slg": cells[22].text.strip(),
                    "obp": cells[23].text.strip(),
                }
            )

        return {"team": team_name, "league": league, "players": players}
    except Exception as e:
        print(f"Error getting batting stats for {season}/{team_code}: {e}")
        return {"team": "", "league": "", "players": []}


def get_pitching_stats(season: int, team_code: str) -> dict:
    try:
        url = f"https://npb.jp/bis/eng/{season}/stats/idp1_{team_code}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        title_div = soup.select_one("div#stdivtitle h1")
        team_name = (
            title_div.text.strip().replace("\n", "").strip() if title_div else ""
        )

        league_tag = soup.select_one("div#stdivtitle h2")
        league = league_tag.text.strip() if league_tag else ""

        pitchers = []
        for row in soup.select("tr.ststats"):
            cells = row.find_all("td")
            if len(cells) < 24:
                continue

            name = cells[1].text.strip()
            if not name:
                continue

            # IP is split across two cells - combine them
            ip_whole = cells[11].text.strip()
            ip_frac = cells[12].text.strip()
            if ip_frac and ip_frac != "\xa0":
                ip = f"{ip_whole}{ip_frac}"
            else:
                ip = ip_whole

            pitchers.append(
                {
                    "name": name,
                    "games": cells[2].text.strip(),
                    "wins": cells[3].text.strip(),
                    "losses": cells[4].text.strip(),
                    "saves": cells[5].text.strip(),
                    "holds": cells[6].text.strip(),
                    "cg": cells[7].text.strip(),
                    "sho": cells[8].text.strip(),
                    "pct": cells[9].text.strip(),
                    "bf": cells[10].text.strip(),
                    "ip": ip,
                    "hits": cells[13].text.strip(),
                    "hr": cells[14].text.strip(),
                    "bb": cells[15].text.strip(),
                    "ibb": cells[16].text.strip(),
                    "hb": cells[17].text.strip(),
                    "so": cells[18].text.strip(),
                    "wp": cells[19].text.strip(),
                    "bk": cells[20].text.strip(),
                    "runs": cells[21].text.strip(),
                    "er": cells[22].text.strip(),
                    "era": cells[23].text.strip(),
                }
            )

        return {"team": team_name, "league": league, "pitchers": pitchers}
    except Exception as e:
        print(f"Error getting pitching stats for {season}/{team_code}: {e}")
        return {"team": "", "league": "", "pitchers": []}


def get_batting_leaders(season: int, league: str) -> list:
    try:
        # league: 'c' for Central, 'p' for Pacific
        url = f"https://npb.jp/bis/eng/{season}/stats/bat_{league}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        players = []
        for row in soup.select("tr.ststats"):
            cells = row.find_all("td")
            if len(cells) < 25:
                continue
            players.append(
                {
                    "rank": cells[0].text.strip(),
                    "name": cells[1].text.strip(),
                    "team": cells[2].text.strip(),
                    "avg": cells[3].text.strip(),
                    "games": cells[4].text.strip(),
                    "pa": cells[5].text.strip(),
                    "ab": cells[6].text.strip(),
                    "runs": cells[7].text.strip(),
                    "hits": cells[8].text.strip(),
                    "doubles": cells[9].text.strip(),
                    "triples": cells[10].text.strip(),
                    "hr": cells[11].text.strip(),
                    "tb": cells[12].text.strip(),
                    "rbi": cells[13].text.strip(),
                    "sb": cells[14].text.strip(),
                    "cs": cells[15].text.strip(),
                    "sh": cells[16].text.strip(),
                    "sf": cells[17].text.strip(),
                    "bb": cells[18].text.strip(),
                    "ibb": cells[19].text.strip(),
                    "hp": cells[20].text.strip(),
                    "so": cells[21].text.strip(),
                    "gdp": cells[22].text.strip(),
                    "slg": cells[23].text.strip(),
                    "obp": cells[24].text.strip(),
                }
            )

        return players
    except Exception as e:
        print(f"Error getting batting leaders for {season}/{league}: {e}")
        return []


def get_pitching_leaders(season: int, league: str) -> dict:
    try:
        url = f"https://npb.jp/bis/eng/{season}/stats/pit_{league}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        # Three tables: starters, closers, setuppers
        tables = soup.select("table")
        sections = ["starters", "closers", "setuppers"]
        result = {}

        for i, table in enumerate(tables[:3]):
            section = sections[i]
            pitchers = []
            for row in table.select("tr.ststats"):
                cells = row.find_all("td")
                if len(cells) < 24:
                    continue

                ip_whole = cells[13].text.strip()
                ip_frac = cells[14].text.strip()
                ip = (
                    f"{ip_whole}{ip_frac}"
                    if ip_frac and ip_frac != "\xa0"
                    else ip_whole
                )

                pitchers.append(
                    {
                        "rank": cells[0].text.strip(),
                        "name": cells[1].text.strip(),
                        "team": cells[2].text.strip(),
                        "era": cells[3].text.strip(),
                        "games": cells[4].text.strip(),
                        "wins": cells[5].text.strip(),
                        "losses": cells[6].text.strip(),
                        "saves": cells[7].text.strip(),
                        "holds": cells[8].text.strip(),
                        "cg": cells[9].text.strip(),
                        "sho": cells[10].text.strip(),
                        "pct": cells[11].text.strip(),
                        "bf": cells[12].text.strip(),
                        "ip": ip,
                        "hits": cells[15].text.strip(),
                        "hr": cells[16].text.strip(),
                        "bb": cells[17].text.strip(),
                        "ibb": cells[18].text.strip(),
                        "hb": cells[19].text.strip(),
                        "so": cells[20].text.strip(),
                        "wp": cells[21].text.strip(),
                        "bk": cells[22].text.strip(),
                        "runs": cells[23].text.strip(),
                        "er": cells[24].text.strip(),
                    }
                )
            result[section] = pitchers

        return result
    except Exception as e:
        print(f"Error getting pitching leaders for {season}/{league}: {e}")
        return {"starters": [], "closers": [], "setuppers": []}


def get_box_score(season: int, game_id: str) -> dict:
    try:
        # Try new URL pattern first
        url = f"https://npb.jp/bis/eng/{season}/{game_id}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            url = f"https://npb.jp/bis/eng/{season}/games/{game_id}.html"
            response = requests.get(url, headers=headers)

            soup = BeautifulSoup(response.content, "html.parser")

            # Date
            date_tag = soup.select_one("div#gmdivtitle h1")
            date_str = date_tag.text.strip() if date_tag else ""

            # Venue and attendance
            info_div = soup.select_one("div#gmdivinfo")
            venue = ""
            attendance = ""
            if info_div:
                tds = info_div.find_all("td")
                if tds:
                    venue = tds[0].text.strip()
                if len(tds) > 1:
                    full_info = tds[1].text.strip()
                    if "Att." in full_info:
                        att_start = full_info.index("Att.")
                        attendance = full_info[att_start:].strip()

            # Game number
            game_num_div = soup.select_one("div.gmdivnumber")
            game_number = game_num_div.text.strip() if game_num_div else ""

            # Score summary — get unique teams only, max 2
            teams_summary = []
            score_div = soup.select_one("div#gmdivscore")
            if score_div:
                for row in score_div.select("tr"):
                    name_td = row.select_one("td.contentshdname")
                    run_td = row.select_one("td.gmboxrun")
                    if name_td and run_td:
                        entry = {
                            "team": name_td.text.strip(),
                            "runs": run_td.text.strip(),
                        }
                        if entry not in teams_summary:
                            teams_summary.append(entry)

            # Line score
            line_score = []
            result_table = soup.select_one("div#gmdivresult table")
            if result_table:
                rows = result_table.select("tr")
                for row in rows[1:]:
                    cells = row.find_all("td")
                    if not cells:
                        continue
                    team_name = cells[0].text.strip()
                    innings = [c.text.strip() for c in cells[1:-3]]
                    r = cells[-3].text.strip()
                    h = cells[-2].text.strip()
                    e = cells[-1].text.strip()
                    line_score.append(
                        {"team": team_name, "innings": innings, "r": r, "h": h, "e": e}
                    )

            # WP/LP
            wp = ""
            lp = ""
            pit_div = soup.select_one("div#gmdivpit")
            if pit_div:
                for row in pit_div.select("tr"):
                    label = row.select_one("td.gmresunm")
                    value = row.select_one("td.gmresults")
                    if label and value:
                        if "WP" in label.text:
                            wp = value.text.strip()
                        elif "LP" in label.text:
                            lp = value.text.strip()

            # HR
            hr = ""
            hr_div = soup.select_one("div#gmdivhr")
            if hr_div:
                hr_val = hr_div.select_one("td.gmresults")
                if hr_val:
                    hr = hr_val.text.strip()

            # Team names from box score headers — exactly 2
            team_headers = [th.text.strip() for th in soup.select("td.gmtblteam")][:2]

            # Get the main box score table container
            gmdivtbl = soup.select_one("div#gmdivtbl")

            # Batting and pitching tables are side by side in td.gmcolorsub
            batting_boxes = []
            pitching_boxes = []

            if gmdivtbl:
                # Each team's data is in a td.gmcolorsub column
                columns = gmdivtbl.select("td.gmcolorsub")

                # Columns come in pairs: [away_batter, home_batter, away_pitcher, home_pitcher]
                # But actually layout is: top row has team headers,
                # middle row has batting side by side, bottom row has pitching side by side

                batter_cols = []
                pitcher_cols = []

                for col in columns:
                    has_batters = bool(col.select("td.gmbatter"))
                    has_pitchers = bool(col.select("td.gmpitcher"))
                    if has_batters:
                        batter_cols.append(col)
                    elif has_pitchers:
                        pitcher_cols.append(col)

                # Batting boxes — only use gmbatter rows, not gmnxtbatter
                for i, col in enumerate(batter_cols[:2]):
                    team_name = team_headers[i] if i < len(team_headers) else ""
                    batters = []
                    for row in col.select("tr.gmstats"):
                        name_td = row.select_one("td.gmbatter, td.gmnxtbatter")
                        cells = row.find_all("td")
                        if name_td and len(cells) >= 7:
                            name_link = cells[0].find("a")
                            player_id = (
                                name_link["href"].split("/")[-1].replace(".html", "")
                                if name_link
                                else ""
                            )
                            batters.append(
                                {
                                    "name": cells[0].text.strip(),
                                    "ab": cells[1].text.strip(),
                                    "h": cells[2].text.strip(),
                                    "rbi": cells[3].text.strip(),
                                    "bb": cells[4].text.strip(),
                                    "hp": cells[5].text.strip(),
                                    "so": cells[6].text.strip(),
                                }
                            )
                    batting_boxes.append({"team": team_name, "batters": batters})

                # Pitching boxes
                for i, col in enumerate(pitcher_cols[:2]):
                    team_name = team_headers[i] if i < len(team_headers) else ""
                    pitchers = []
                    for row in col.select("tr.gmstats"):
                        name_td = row.select_one("td.gmpitcher")
                        cells = row.find_all("td")
                        if name_td and len(cells) >= 9:
                            name_link = cells[0].find("a")
                            player_id = (
                                name_link["href"].split("/")[-1].replace(".html", "")
                                if name_link
                                else ""
                            )
                            ip_whole = cells[1].text.strip()
                            ip_frac = cells[2].text.strip()
                            ip = (
                                f"{ip_whole}{ip_frac}"
                                if ip_frac and ip_frac != "\xa0"
                                else ip_whole
                            )
                            pitchers.append(
                                {
                                    "name": cells[0].text.strip(),
                                    "ip": ip,
                                    "bf": cells[3].text.strip(),
                                    "h": cells[4].text.strip(),
                                    "bb": cells[5].text.strip(),
                                    "hb": cells[6].text.strip(),
                                    "so": cells[7].text.strip(),
                                    "er": cells[8].text.strip(),
                                }
                            )
                    pitching_boxes.append({"team": team_name, "pitchers": pitchers})

            return {
                "date": date_str,
                "venue": venue,
                "attendance": attendance,
                "game_number": game_number,
                "teams": teams_summary,
                "line_score": line_score,
                "wp": wp,
                "lp": lp,
                "hr": hr,
                "batting": batting_boxes,
                "pitching": pitching_boxes,
            }
    except Exception as e:
        print(f"Error getting box score for {season}/{game_id}: {e}")
        return {
            "date": "",
            "venue": "",
            "attendance": "",
            "game_number": "",
            "teams": [],
            "line_score": [],
            "wp": "",
            "lp": "",
            "hr": "",
            "batting": [],
            "pitching": [],
        }


def season_has_data(season: int) -> bool:
    """Check if a season has data available on npb.jp"""
    url = f"https://npb.jp/bis/eng/{season}/standings/index.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        return response.status_code == 200 and "standings" in response.text.lower()
    except:
        return False


def get_roster(team_code: str) -> dict:
    try:
        url = f"https://npb.jp/bis/eng/teams/rst_{team_code}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        # Team name
        title_tag = soup.select_one("td.tenametitle h1")
        team_name = title_tag.text.strip() if title_tag else ""

        result = {
            "team": team_name,
            "manager": [],
            "pitchers": [],
            "catchers": [],
            "infielders": [],
            "outfielders": [],
            "developmental": [],
        }

        # Only parse the main roster table (first rosterlisttbl)
        main_table = soup.select("table.rosterlisttbl")[0]
        current_section = None

        for row in main_table.select("tr"):
            header = row.select_one("th.rosterPos")
            if header:
                text = header.text.strip().upper()
                if "MANAGER" in text:
                    current_section = "manager"
                elif "PITCHER" in text:
                    current_section = "pitchers"
                elif "CATCHER" in text:
                    current_section = "catchers"
                elif "INFIELDER" in text:
                    current_section = "infielders"
                elif "OUTFIELDER" in text:
                    current_section = "outfielders"
                continue

            name_td = row.select_one("td.rosterRegister")
            if not name_td or not current_section:
                continue

            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            number = cells[0].text.strip()
            name_tag = name_td.find("a")
            name = name_tag.text.strip() if name_tag else name_td.text.strip()
            player_id = ""
            if name_tag and name_tag.get("href"):
                # href is like /bis/eng/players/31135138.html
                player_id = name_tag["href"].split("/")[-1].replace(".html", "")

            if current_section == "manager":
                born = cells[2].text.strip() if len(cells) > 2 else ""
                result["manager"].append(
                    {
                        "number": number,
                        "name": name,
                        "player_id": "",
                        "position": "Manager",
                        "born": born,
                        "height": "",
                        "weight": "",
                        "throws": "",
                        "bats": "",
                        "note": "",
                    }
                )
            else:
                born = cells[2].text.strip() if len(cells) > 2 else ""
                height = cells[3].text.strip() if len(cells) > 3 else ""
                weight = cells[4].text.strip() if len(cells) > 4 else ""
                throws = cells[5].text.strip() if len(cells) > 5 else ""
                bats = cells[6].text.strip() if len(cells) > 6 else ""
                note_td = row.select_one("td.rosterdetail")
                note = note_td.text.strip() if note_td else ""

                pos_map = {
                    "pitchers": "P",
                    "catchers": "C",
                    "infielders": "INF",
                    "outfielders": "OF",
                }
                result[current_section].append(
                    {
                        "number": number,
                        "name": name,
                        "player_id": player_id,
                        "position": pos_map.get(current_section, ""),
                        "born": born,
                        "height": height,
                        "weight": weight,
                        "throws": throws,
                        "bats": bats,
                        "note": note,
                    }
                )

        # Separate developmental squad — numbers >= 100 are typically dev squad
        # Better: re-parse using div sections
        all_sections = soup.select("div.rosterSub")
        if all_sections:
            # Find the developmental table — it comes after div.rosterSub
            dev_div = all_sections[0]
            dev_table = dev_div.find_next("table", class_="rosterlisttbl")
            if dev_table:
                dev_section = None
                for row in dev_table.select("tr"):
                    header = row.select_one("th.rosterPos")
                    if header:
                        text = header.text.strip().upper()
                        if "PITCHER" in text:
                            dev_section = "P"
                        elif "CATCHER" in text:
                            dev_section = "C"
                        elif "INFIELDER" in text:
                            dev_section = "INF"
                        elif "OUTFIELDER" in text:
                            dev_section = "OF"
                        continue

                    name_td = row.select_one("td.rosterRegister")
                    if not name_td or not dev_section:
                        continue

                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue

                    number = cells[0].text.strip()
                    name_tag = name_td.find("a")
                    name = name_tag.text.strip() if name_tag else name_td.text.strip()
                    born = cells[2].text.strip() if len(cells) > 2 else ""
                    height = cells[3].text.strip() if len(cells) > 3 else ""
                    weight = cells[4].text.strip() if len(cells) > 4 else ""
                    throws = cells[5].text.strip() if len(cells) > 5 else ""
                    bats = cells[6].text.strip() if len(cells) > 6 else ""
                    note_td = row.select_one("td.rosterdetail")
                    note = note_td.text.strip() if note_td else ""

                    result["developmental"].append(
                        {
                            "number": number,
                            "name": name,
                            "player_id": player_id,
                            "position": dev_section,
                            "born": born,
                            "height": height,
                            "weight": weight,
                            "throws": throws,
                            "bats": bats,
                            "note": note,
                        }
                    )

        return result

    except Exception as e:
        print(f"Error getting roster for {team_code}: {e}")
        return {
            "team": "",
            "manager": [],
            "pitchers": [],
            "catchers": [],
            "infielders": [],
            "outfielders": [],
            "developmental": [],
        }


def get_player(player_id: str) -> dict:
    try:
        url = f"https://npb.jp/bis/eng/players/{player_id}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        # Name, number, team — in div#pc_v_name
        number = ""
        name = ""
        team = ""
        name_div = soup.select_one("div#pc_v_name")
        if name_div:
            items = name_div.select("ul li")
            for item in items:
                text = item.text.strip()
                if re.match(r"^\d+$", text):
                    number = text
                elif any(
                    x in text
                    for x in [
                        "Giants",
                        "Tigers",
                        "BayStars",
                        "Carp",
                        "Swallows",
                        "Dragons",
                        "Hawks",
                        "Fighters",
                        "Buffaloes",
                        "Eagles",
                        "Lions",
                        "Marines",
                    ]
                ):
                    team = text
                elif text and len(text) > 1:
                    name = text

        # Photo URL
        photo_tag = soup.find("img", src=lambda s: s and "players_photo" in s)
        if photo_tag:
            src = photo_tag["src"]
            photo_url = src if src.startswith("http") else f"https://p.npb.jp{src}"
        else:
            photo_url = ""

        # Bio — first table on page, uses <th> for labels
        position = ""
        bats_throws = ""
        height_weight = ""
        born = ""
        all_tables = soup.select("table")
        if all_tables:
            bio_table = all_tables[0]
            for row in bio_table.select("tr"):
                th = row.find("th")
                td = row.find("td")
                if th and td:
                    label = th.text.strip()
                    value = td.text.strip()
                    if label == "Position":
                        position = value
                    elif label == "Bats / Throws":
                        bats_throws = value
                    elif label == "Height / Weight":
                        height_weight = value
                    elif label == "Born":
                        born = value

        # Build IP lookup from table.table_inning elements
        ip_values = []
        for t in soup.select("table.table_inning"):
            whole = t.select_one("th")
            frac = t.select_one("td")
            whole_str = whole.text.strip() if whole else ""
            frac_str = frac.text.strip() if frac else ""
            frac_str = frac_str if frac_str in [".1", ".2"] else ""
            ip_values.append(f"{whole_str}{frac_str}")

        # Remove table_inning from DOM so they don't add extra cells
        for t in soup.select("table.table_inning"):
            t.decompose()

        # Stats tables
        pitching_stats = []
        batting_stats = []
        pitching_ip_index = 0

        for table in soup.select("table"):
            header_cells = table.select("thead tr th")
            if not header_cells:
                continue
            headers = [th.text.strip() for th in header_cells]
            if "Year" not in headers:
                continue

            is_pitching = "ERA" in headers
            is_batting = "AVG" in headers

            for row in table.select("tbody tr"):
                cells = row.find_all("td")
                if not cells or len(cells) < 3:
                    continue
                year = cells[0].text.strip()
                if not year or not re.match(r"^\d{4}$", year):
                    continue

                if is_pitching:
                    ip = (
                        ip_values[pitching_ip_index]
                        if pitching_ip_index < len(ip_values)
                        else ""
                    )
                    pitching_ip_index += 1
                    pitching_stats.append(
                        {
                            "year": year,
                            "team": cells[1].text.strip(),
                            "g": cells[2].text.strip(),
                            "w": cells[3].text.strip(),
                            "l": cells[4].text.strip(),
                            "sv": cells[5].text.strip(),
                            "hld": cells[6].text.strip(),
                            "hp": cells[7].text.strip(),
                            "cg": cells[8].text.strip(),
                            "sho": cells[9].text.strip(),
                            "pct": cells[10].text.strip(),
                            "bf": cells[11].text.strip(),
                            "ip": ip,
                            # cells[12] is the now-empty IP cell, skip it
                            "h": cells[13].text.strip(),
                            "hr": cells[14].text.strip(),
                            "bb": cells[15].text.strip(),
                            "hb": cells[16].text.strip(),
                            "so": cells[17].text.strip(),
                            "wp": cells[18].text.strip(),
                            "bk": cells[19].text.strip(),
                            "r": cells[20].text.strip(),
                            "er": cells[21].text.strip(),
                            "era": cells[22].text.strip() if len(cells) > 22 else "",
                        }
                    )

                elif is_batting:
                    batting_stats.append(
                        {
                            "year": year,
                            "team": cells[1].text.strip(),
                            "g": cells[2].text.strip(),
                            "pa": cells[3].text.strip(),
                            "ab": cells[4].text.strip(),
                            "r": cells[5].text.strip(),
                            "h": cells[6].text.strip(),
                            "doubles": cells[7].text.strip(),
                            "triples": cells[8].text.strip(),
                            "hr": cells[9].text.strip(),
                            "tb": cells[10].text.strip(),
                            "rbi": cells[11].text.strip(),
                            "sb": cells[12].text.strip(),
                            "cs": cells[13].text.strip(),
                            "sh": cells[14].text.strip(),
                            "sf": cells[15].text.strip(),
                            "bb": cells[16].text.strip(),
                            "hp": cells[17].text.strip(),
                            "so": cells[18].text.strip(),
                            "gdp": cells[19].text.strip(),
                            "avg": cells[20].text.strip(),
                            "slg": cells[21].text.strip() if len(cells) > 21 else "",
                            "obp": cells[22].text.strip() if len(cells) > 22 else "",
                        }
                    )

        return {
            "player_id": player_id,
            "number": number,
            "name": name,
            "team": team,
            "position": position,
            "bats_throws": bats_throws,
            "height_weight": height_weight,
            "born": born,
            "photo_url": photo_url,
            "pitching_stats": pitching_stats,
            "batting_stats": batting_stats,
        }

    except Exception as e:
        print(f"Error getting player {player_id}: {e}")
        return {
            "player_id": player_id,
            "number": "",
            "name": "",
            "team": "",
            "position": "",
            "bats_throws": "",
            "height_weight": "",
            "born": "",
            "photo_url": "",
            "pitching_stats": [],
            "batting_stats": [],
        }


def get_team_info(team_code: str) -> dict:
    try:
        url = f"https://npb.jp/bis/eng/teams/index_{team_code}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        # Team name — second h1 on page
        team_name = ""
        h1_tags = soup.select("h1")
        if len(h1_tags) >= 2:
            team_name = h1_tags[1].text.strip()
        elif h1_tags:
            team_name = h1_tags[0].text.strip()

        # Website URL
        website = ""
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "jump_" in href and team_code in href:
                website = f"https://npb.jp{href}" if href.startswith("/") else href
                break

        # History name and stadium name — first div is history, second is stadium
        teinfdtl_divs = soup.select("div.teinfdtl")
        history_name = teinfdtl_divs[0].text.strip() if len(teinfdtl_divs) > 0 else ""
        stadium_name = teinfdtl_divs[1].text.strip() if len(teinfdtl_divs) > 1 else ""

        # Stadium address
        stadium_address = ""
        for td in soup.select("td.teinfttl"):
            if "Address" in td.text:
                next_td = td.find_next_sibling("td")
                if next_td:
                    stadium_address = next_td.text.strip()

        # Championships — find Team History h2 then parse the content table
        # Get all dt/dd children of the main dl
        main_dl = soup.select("dl")[4]
        children = [c for c in main_dl.children if c.name in ["dt", "dd"]]

        cl_championships = ""
        japan_championships = ""

        for i, child in enumerate(children):
            if child.name == "dt" and "Team History" in child.text:
                # The next sibling dd contains the history content
                if i + 1 < len(children):
                    history_dd = children[i + 1]
                    for row in history_dd.select("tr"):
                        label_td = row.select_one("td.teinfttl")
                        if not label_td:
                            continue
                        label = label_td.text.strip()
                        count_td = row.select_one("td.teinfnum")
                        count = count_td.text.strip() if count_td else ""
                        years_tds = row.select("td.teinfdtl")
                        years = years_tds[-1].text.strip() if years_tds else ""
                        if "Central League Champions" in label:
                            cl_championships = f"{count} — {years}"
                        elif "Pacific League Champions" in label:
                            cl_championships = f"{count} — {years}"
                        elif "Nippon Champions" in label:
                            japan_championships = f"{count} — {years}"

        return {
            "team_code": team_code,
            "team_name": team_name,
            "history_name": history_name,
            "website": website,
            "cl_championships": cl_championships,
            "japan_championships": japan_championships,
            "stadium_name": stadium_name,
            "stadium_address": stadium_address,
        }

    except Exception as e:
        print(f"Error getting team info for {team_code}: {e}")
        return {
            "team_code": team_code,
            "team_name": "",
            "history_name": "",
            "website": "",
            "cl_championships": "",
            "japan_championships": "",
            "stadium_name": "",
            "stadium_address": "",
        }


def get_team_schedule(team_code: str, month: str) -> dict:
    try:
        url = f"https://npb.jp/bis/eng/teams/calendar_{team_code}_{month}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        # Title
        title = ""
        for td in soup.select("td"):
            if (
                "Calendar" in td.text
                and "2026" in td.text
                and len(td.text.strip()) < 50
            ):
                title = td.text.strip()
                break

        # Use table.tetblmain
        cal_table = soup.select_one("table.tetblmain")
        if not cal_table:
            return {
                "team_code": team_code,
                "month": month,
                "title": title,
                "games": [],
                "days": [],
            }

        tc = team_code.upper()
        # DB is special case
        if team_code == "db":
            tc = "DB"

        days = []
        for cell in cal_table.select("td.teschedule"):
            day_div = cell.select_one("div.teschedate")
            day = day_div.text.strip() if day_div else ""
            if not day:
                continue

            game = None
            vs_div = cell.select_one("div.tevsteam")
            if vs_div:
                score_div = vs_div.select_one("div.tescore")
                venue_div = vs_div.select_one("div.testdm")
                time_div = vs_div.select_one("div.tetime")

                matchup = score_div.text.strip() if score_div else ""
                venue = venue_div.text.strip().strip("()") if venue_div else ""
                time = time_div.text.strip() if time_div else ""

                # Parse home/away
                is_home = False
                opponent = ""
                if " - " in matchup:
                    parts = matchup.split(" - ")
                    home_code = parts[0].strip()
                    away_code = parts[1].strip()
                    is_home = home_code == tc
                    opponent = away_code if is_home else home_code

                # Check for score link (past games)
                game_id = ""
                score_link = vs_div.select_one("a")
                if score_link and score_link.get("href"):
                    href = score_link["href"]
                    game_id = href.split("/")[-1].replace(".html", "")

                # Check for actual score
                score_text = score_div.text.strip() if score_div else ""
                home_score = ""
                away_score = ""
                # Score format changes to "3 - 5" when game is played
                if score_text and all(c.isdigit() or c in " -" for c in score_text):
                    score_parts = score_text.split(" - ")
                    if len(score_parts) == 2:
                        home_score = score_parts[0].strip()
                        away_score = score_parts[1].strip()

                game = {
                    "opponent": opponent,
                    "is_home": is_home,
                    "venue": venue,
                    "time": time,
                    "game_id": game_id,
                    "home_score": home_score,
                    "away_score": away_score,
                    "matchup": matchup,
                }

            days.append(
                {
                    "day": day,
                    "game": game,
                }
            )

        return {
            "team_code": team_code,
            "month": month,
            "title": title,
            "days": days,
        }

    except Exception as e:
        print(f"Error getting team schedule for {team_code}/{month}: {e}")
        return {
            "team_code": team_code,
            "month": month,
            "title": "",
            "days": [],
        }


# ✅ Routes defined AFTER
@app.get("/standings")
def standings_current():
    season = 2026
    if not season_has_data(season):
        season = 2025
    return get_standings(season)


@app.get("/standings/{season}")
def standings_by_season(season: int):
    if not season_has_data(season):
        season = season - 1
    return get_standings(season)


@app.get("/schedule/{year}/{month}/{day}")
def schedule_by_date(year: int, month: int, day: int):
    result = get_schedule_by_date(year, month, day)
    if not result:
        return []
    return result


@app.get("/stats/batting/{season}/{team_code}")
def batting_stats(season: int, team_code: str):
    if not season_has_data(season):
        season = season - 1
    return get_batting_stats(season, team_code)


@app.get("/stats/pitching/{season}/{team_code}")
def pitching_stats(season: int, team_code: str):
    if not season_has_data(season):
        season = season - 1
    return get_pitching_stats(season, team_code)


@app.get("/leaders/batting/{season}/{league}")
def batting_leaders(season: int, league: str):
    if not season_has_data(season):
        season = season - 1
    return get_batting_leaders(season, league)


@app.get("/leaders/pitching/{season}/{league}")
def pitching_leaders(season: int, league: str):
    if not season_has_data(season):
        season = season - 1
    return get_pitching_leaders(season, league)


@app.get("/boxscore/{season}/{game_id}")
def box_score(season: int, game_id: str):
    return get_box_score(season, game_id)


@app.get("/roster/{team_code}")
def roster(team_code: str):
    return get_roster(team_code)


@app.get("/player/{player_id}")
def player(player_id: str):
    return get_player(player_id)


@app.get("/players/all")
def all_players():
    global _players_cache, _players_cache_time

    # Return cached result if fresh
    if _players_cache is not None and _players_cache_time is not None:
        if datetime.now() - _players_cache_time < CACHE_DURATION:
            return _players_cache

    team_codes = ["g", "t", "db", "c", "s", "d", "h", "f", "b", "e", "l", "m"]
    result = []
    for code in team_codes:
        roster = get_roster(code)
        for section in ["pitchers", "catchers", "infielders", "outfielders"]:
            for player in roster[section]:
                if player["player_id"]:
                    result.append(
                        {
                            "player_id": player["player_id"],
                            "number": player["number"],
                            "name": player["name"],
                            "team": roster["team"],
                            "team_code": code,
                            "position": player["position"],
                        }
                    )

    _players_cache = result
    _players_cache_time = datetime.now()
    return result


@app.get("/team/{team_code}")
def team_info(team_code: str):
    return get_team_info(team_code)


@app.get("/team/schedule/{team_code}/{month}")
def team_schedule(team_code: str, month: str):
    return get_team_schedule(team_code, month)


# @app.get("/debug2/player/{player_id}")
# def debug2_player(player_id: str):
#     url = f"https://npb.jp/bis/eng/players/{player_id}.html"
#     headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
#     response = requests.get(url, headers=headers, timeout=10)
#     soup = BeautifulSoup(response.content, "html.parser")

#     # Dump all tables and their contents
#     tables = soup.select("table")
#     result = []
#     for i, table in enumerate(tables):
#         result.append({"index": i, "html": str(table)[:500]})
#     return {"table_count": len(tables), "tables": result}


@app.get("/debug/team/{team_code}")
def debug_team(team_code: str):
    url = f"https://npb.jp/bis/eng/teams/index_{team_code}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")

    return {
        "all_dl_count": len(soup.select("dl")),
        "all_dt_texts": [dt.text.strip() for dt in soup.select("dt")],
        "all_h1_texts": [h1.text.strip() for h1 in soup.select("h1")],
        "all_h2_texts": [h2.text.strip() for h2 in soup.select("h2")],
        "all_table_count": len(soup.select("table")),
        "first_dl_html": (
            str(soup.select_one("dl"))[:1000] if soup.select_one("dl") else "none"
        ),
    }


@app.get("/debug2/team/{team_code}")
def debug2_team(team_code: str):
    url = f"https://npb.jp/bis/eng/teams/index_{team_code}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")

    main_dl = soup.select("dl")[4]
    children = [c for c in main_dl.children if c.name in ["dt", "dd"]]

    for i, child in enumerate(children):
        if child.name == "dt" and "Team History" in child.text:
            history_dd = children[i + 1]
            rows = history_dd.select("tr")
            # Return first 3 rows full HTML
            return {"row_count": len(rows), "rows": [str(row) for row in rows[:5]]}
    return {"error": "not found"}


@app.get("/debug/team/schedule/{team_code}/{month}")
def debug_team_schedule(team_code: str, month: str):
    url = f"https://npb.jp/bis/eng/teams/calendar_{team_code}_{month}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")

    # Look at table index 2 - tetblmain
    table = soup.select("table")[2]
    cells = table.select("td")
    result = []
    for i, cell in enumerate(cells[:20]):
        result.append(
            {
                "index": i,
                "class": cell.get("class", ""),
                "text": cell.text.strip()[:200],
                "html": str(cell)[:300],
            }
        )
    return result


@app.get("/debug/schedule/{year}/{month}/{day}")
def debug_schedule(year: int, month: int, day: int):
    url = f"https://npb.jp/bis/eng/{year}/games/gm{year}{month:02d}{day:02d}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    games_div = soup.select_one("div.contents.games")
    return {
        "status": response.status_code,
        "games_div_html": str(games_div)[:3000] if games_div else "none",
    }
