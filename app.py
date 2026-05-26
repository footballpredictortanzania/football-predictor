from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import requests
import math

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

API_KEY = "3b036ca5b48149f1bc1d283626fa3b5b"

def poisson_pmf(k, lamb):
    if lamb <= 0:
        return 0
    return (pow(lamb, k) * math.exp(-lamb)) / math.factorial(k)

@app.route('/api/predict', methods=['POST'])
def predict():
    data = request.json
    league_id = data.get('league_id')
    season = data.get('season')

    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={season}&next=15"
    headers = {
        'x-rapidapi-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    response = requests.get(url, headers=headers)
    fixtures_data = response.json().get('response', [])

    results = []
    
    for item in fixtures_data:
        fixture = item.get('fixture', {})
        teams = item.get('teams', {})
        
        home_team = teams.get('home', {}).get('name')
        away_team = teams.get('away', {}).get('name')
        
        h2h_url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={teams.get('home', {}).get('id')}-{teams.get('away', {}).get('id')}&last=10"
        h2h_response = requests.get(h2h_url, headers=headers).json().get('response', [])

        home_goals, away_goals = 0, 0
        match_count = len(h2h_response)

        if match_count > 0:
            for h2h in h2h_response:
                goals = h2h.get('goals', {})
                home_goals += (goals.get('home') or 0)
                away_goals += (goals.get('away') or 0)
            
            home_exp_goals = home_goals / match_count
            away_exp_goals = away_goals / match_count
        else:
            home_exp_goals = 1.3
            away_exp_goals = 1.1

        home_win_prob = 0
        away_win_prob = 0
        draw_prob = 0
        under_pct = 0
        over_pct = 0

        for x in range(6):
            for y in range(6):
                home_prob = poisson_pmf(x, home_exp_goals)
                away_prob = poisson_pmf(y, away_exp_goals)
                joint_prob = home_prob * away_prob

                if x > y:
                    home_win_prob += joint_prob
                elif x < y:
                    away_win_prob += joint_prob
                else:
                    draw_prob += joint_prob

                if (x + y) < 2.5:
                    under_pct += joint_prob
                else:
                    over_pct += joint_prob

        if home_win_prob > 0.45:
            advice = f"Ushindi kwa {home_team} (1)"
        elif away_win_prob > 0.45:
            advice = f"Ushindi kwa {away_team} (2)"
        else:
            advice = "Inaweza kuwa Droo (X) au GG"

        # Tumesafisha '模Z' hapa chini imekuwa 'Z' ya kawaida kabisa
        raw_date = fixture.get('date', '')
        try:
            formatted_date = datetime.fromisoformat(raw_date.replace('Z', '')).strftime('%d/%m/%Y %H:%M')
        except:
            formatted_date = raw_date

        results.append({
            "date": formatted_date,
            "home": home_team,
            "away": away_team,
            "home_win": round(home_win_prob * 100, 1),
            "draw": round(draw_prob * 100, 1),
            "away_win": round(away_win_prob * 100, 1),
            "home_xg": round(home_exp_goals, 2),
            "away_xg": round(away_exp_goals, 2),
            "under_25": round(under_pct * 100, 1),
            "over_25": round(over_pct * 100, 1),
            "advice": advice
        })
        
    return jsonify({"status": "success", "matches": results})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)