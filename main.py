import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"])

# ✅ Function defined FIRST
def get_standings(season: int = 2026) -> dict:
    url = f"https://npb.jp/bis/eng/{season}/standings/index.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    response = requests.get(url, headers=headers)
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
            teams.append({
                "team": cells[0].text.strip(),
                "games": int(cells[1].text.strip()),
                "wins": int(cells[2].text.strip()),
                "losses": int(cells[3].text.strip()),
                "ties": int(cells[4].text.strip()),
                "pct": cells[5].text.strip(),
                "gb": cells[6].text.strip(),
            })
        
        result[league] = teams
    return result


def get_schedule(year: int, month: int) -> list:
    url = f"https://npb.jp/bis/eng/{year}/games/index_s{month:02d}{year}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    results = []
    
    # Each day has a gmdivmain section with a date header and games
    for day_div in soup.select("div#gmdivmain, div.gmdivsublist"):
        # Get the date from the h1 tag
        date_tag = soup.find("h1")
        if date_tag:
            date_str = date_tag.text.strip()
        else:
            date_str = ""
        
        # Get all games for this day
        for game_div in soup.select("div.contentsgame"):
            rows = game_div.select("tr[align='center']")
            info_rows = game_div.select("tr[valign='top']")
            
            for i, row in enumerate(rows):
                teams = row.select("td.contentsTeam")
                runs = row.select("td.contentsRuns")
                
                if len(teams) < 2:
                    continue
                
                away_team = teams[0].text.strip()
                home_team = teams[1].text.strip()
                away_runs = runs[0].text.strip() if runs else ""
                home_runs = runs[1].text.strip() if len(runs) > 1 else ""
                
                # Get venue and game number from info row
                venue = ""
                game_number = ""
                if i < len(info_rows):
                    info_cells = info_rows[i].select("td.contentsinfo")
                    if len(info_cells) >= 2:
                        game_number = info_cells[0].text.strip()
                        venue = info_cells[1].text.strip()
                
                results.append({
                    "date": date_str,
                    "away_team": teams[1].text.strip(),  # swapped
                    "home_team": teams[0].text.strip(),  # swapped
                    "away_runs": runs[1].text.strip() if len(runs) > 1 else "",  # swapped
                    "home_runs": runs[0].text.strip() if runs else "",  # swapped
                    "venue": venue,
                    "game_number": game_number,
                    })
        break  # only process once since it's a single day page
    
    return results


def get_schedule_by_date(year: int, month: int, day: int) -> list:
    url = f"https://npb.jp/bis/eng/{year}/games/gm{year}{month:02d}{day:02d}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    results = []
    
    # Get the date from the correct h1 inside gmdivtitle
    date_tag = soup.select_one("div#gmdivtitle h1")
    date_str = date_tag.text.strip() if date_tag else f"{year}-{month:02d}-{day:02d}"
    # Clean up the image alt text that gets included
    date_str = date_str.replace("\n", "").strip()
    
    for game_div in soup.select("div.contentsgame"):
        rows = game_div.select("tr[align='center']")
        info_rows = game_div.select("tr[valign='top']")
        
        for i, row in enumerate(rows):
            teams = row.select("td.contentsTeam")
            runs = row.select("td.contentsRuns")
            
            if len(teams) < 2:
                continue
            
            away_team = teams[0].text.strip()
            home_team = teams[1].text.strip()
            away_runs = runs[0].text.strip() if runs else ""
            home_runs = runs[1].text.strip() if len(runs) > 1 else ""
            
            venue = ""
            game_number = ""
            if i < len(info_rows):
                info_cells = info_rows[i].select("td.contentsinfo")
                if len(info_cells) >= 2:
                    game_link_tag = info_cells[0].find("a")
                    game_number = info_cells[0].text.strip()
                    game_id = game_link_tag["href"].replace(".html", "") if game_link_tag else ""
                    venue = info_cells[1].text.strip()
            
            results.append({
                "date": date_str,
                "away_team": teams[1].text.strip(),  # swapped
                "home_team": teams[0].text.strip(),  # swapped
                "away_runs": runs[1].text.strip() if len(runs) > 1 else "",  # swapped
                "home_runs": runs[0].text.strip() if runs else "",  # swapped
                "venue": venue,
                "game_number": game_number,
                "game_id": game_id,
                })
    
    return results


def get_batting_stats(season: int, team_code: str) -> dict:
    url = f"https://npb.jp/bis/eng/{season}/stats/idb1_{team_code}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    
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
            
        players.append({
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
        })
    
    return {
        "team": team_name,
        "league": league,
        "players": players
    }
    
def get_pitching_stats(season: int, team_code: str) -> dict:
    url = f"https://npb.jp/bis/eng/{season}/stats/idp1_{team_code}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    title_div = soup.select_one("div#stdivtitle h1")
    team_name = title_div.text.strip().replace("\n", "").strip() if title_div else ""
    
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
        
        pitchers.append({
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
        })
    
    return {
        "team": team_name,
        "league": league,
        "pitchers": pitchers
    }
    
def get_batting_leaders(season: int, league: str) -> list:
    # league: 'c' for Central, 'p' for Pacific
    url = f"https://npb.jp/bis/eng/{season}/stats/bat_{league}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    players = []
    for row in soup.select("tr.ststats"):
        cells = row.find_all("td")
        if len(cells) < 25:
            continue
        players.append({
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
        })
    
    return players


def get_pitching_leaders(season: int, league: str) -> dict:
    url = f"https://npb.jp/bis/eng/{season}/stats/pit_{league}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    
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
            ip = f"{ip_whole}{ip_frac}" if ip_frac and ip_frac != "\xa0" else ip_whole
            
            pitchers.append({
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
            })
        result[section] = pitchers
    
    return result

def get_box_score(season: int, game_id: str) -> dict:
    url = f"https://npb.jp/bis/eng/{season}/games/{game_id}.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    
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
                    "runs": run_td.text.strip()
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
            line_score.append({
                "team": team_name,
                "innings": innings,
                "r": r,
                "h": h,
                "e": e
            })
    
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
                    batters.append({
                        "name": cells[0].text.strip(),
                        "ab": cells[1].text.strip(),
                        "h": cells[2].text.strip(),
                        "rbi": cells[3].text.strip(),
                        "bb": cells[4].text.strip(),
                        "hp": cells[5].text.strip(),
                        "so": cells[6].text.strip(),
                    })
            batting_boxes.append({"team": team_name, "batters": batters})
        
        # Pitching boxes
        for i, col in enumerate(pitcher_cols[:2]):
            team_name = team_headers[i] if i < len(team_headers) else ""
            pitchers = []
            for row in col.select("tr.gmstats"):
                name_td = row.select_one("td.gmpitcher")
                cells = row.find_all("td")
                if name_td and len(cells) >= 9:
                    ip_whole = cells[1].text.strip()
                    ip_frac = cells[2].text.strip()
                    ip = f"{ip_whole}{ip_frac}" if ip_frac and ip_frac != "\xa0" else ip_whole
                    pitchers.append({
                        "name": cells[0].text.strip(),
                        "ip": ip,
                        "bf": cells[3].text.strip(),
                        "h": cells[4].text.strip(),
                        "bb": cells[5].text.strip(),
                        "hb": cells[6].text.strip(),
                        "so": cells[7].text.strip(),
                        "er": cells[8].text.strip(),
                    })
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
    

# ✅ Routes defined AFTER
@app.get("/standings")
def standings_current():
    return get_standings(2026)

@app.get("/standings/{season}")
def standings_by_season(season: int):
    return get_standings(season)

@app.get("/schedule/{year}/{month}")
def schedule_by_month(year: int, month: int):
    return get_schedule(year, month)

@app.get("/schedule/{year}/{month}/{day}")
def schedule_by_date(year: int, month: int, day: int):
    return get_schedule_by_date(year, month, day)

@app.get("/stats/batting/{season}/{team_code}")
def batting_stats(season: int, team_code: str):
    return get_batting_stats(season, team_code)

@app.get("/stats/pitching/{season}/{team_code}")
def pitching_stats(season: int, team_code: str):
    return get_pitching_stats(season, team_code)

@app.get("/leaders/batting/{season}/{league}")
def batting_leaders(season: int, league: str):
    return get_batting_leaders(season, league)

@app.get("/leaders/pitching/{season}/{league}")
def pitching_leaders(season: int, league: str):
    return get_pitching_leaders(season, league)

@app.get("/boxscore/{season}/{game_id}")
def box_score(season: int, game_id: str):
    return get_box_score(season, game_id)
