import requests
from bs4 import BeautifulSoup

def get_standings(season: int = 2026) -> dict:
    url = f"https://npb.jp/bis/eng/{season}/standings/index.html"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    result = {}
    
    for table in soup.select("table.standings"):
        # Determine league from header cell
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
            tr = row.parent  # get the <tr>
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

# Test it
if __name__ == "__main__":
    import json
    # Use 2025 since 2026 season hasn't started yet
    standings = get_standings(2025)
    print(json.dumps(standings, indent=2))