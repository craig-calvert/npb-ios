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
    
    return results


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

