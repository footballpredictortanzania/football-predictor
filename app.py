from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import requests
from scipy.stats import poisson

app = Flask(__name__)
CORS(app)

API_KEY = "d0f9b7d74b61b2830933dd0572c555a2"
HEADERS = {'x-apisports-key': API_KEY}

def get_team_goal_averages(league_id, season, team_id, side='home'):
    url = "https://v3.football.api-sports.io/teams/statistics"
    params = {'league': league_id, 'season': season, 'team': team_id}
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    if response.status_code != 200 or not data.get('response'):
        return None, None
    stats = data['response']['goals']
    avg_scored = float(stats['for']['average'][side])
    avg_conceded = float(stats['against']['average'][side])
    return avg_scored, avg_conceded

def get_today_fixtures(league_id, season):
    url = "https://v3.football.api-sports.io/fixtures"
    today_date = datetime.now().strftime('%Y-%m-%d')
    params = {'league': league_id, 'season': season, 'date': today_date}
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    if response.status_code != 200 or not data.get('response'):
        return []
    return data['response']

def calculate_poisson(home_exp_goals, away_exp_goals, line=2.5):
    under_prob = 0.0
    over_prob = 0.0
    for home_goals in range(11):
        for away_goals in range(11):
            p_home = poisson.pmf(home_goals, home_exp_goals)
            p_away = poisson.pmf(away_goals, away_exp_goals)
            prob_scoreline = p_home * p_away
            if (home_goals + away_goals) < line:
                under_prob += prob_scoreline
            else:
                over_prob += prob_scoreline
    return under_prob * 100, over_prob * 100

@app.route('/api/predict', methods=['POST'])
def get_predictions():
    req_data = request.json
    league_id = req_data.get('league_id', 135)
    season = req_data.get('season', 2025)
    
    fixtures = get_today_fixtures(league_id, season)
    
    if not fixtures:
        return jsonify({"status": "empty", "message": "Ratiba haina mechi yoyote kwenye ligi hii kwa siku ya leo."})
    
    results = []
    for match in fixtures:
        home_id = match['teams']['home']['id']
        home_name = match['teams']['home']['name']
        away_id = match['teams']['away']['id']
        away_name = match['teams']['away']['name']
        
        home_scored, home_conceded = get_team_goal_averages(league_id, season, home_id, side='home')
        away_scored, away_conceded = get_team_goal_averages(league_id, season, away_id, side='away')
        
        if None in [home_scored, home_conceded, away_scored, away_conceded]:
            continue
            
        home_exp_goals = (home_scored + away_conceded) / 2
        away_exp_goals = (away_scored + home_conceded) / 2
        
        under_pct, over_pct = calculate_poisson(home_exp_goals, away_exp_goals)
        
        advice = "No clear trend"
        if over_pct > 65.0:
            advice = "🔥 OVER 2.5 (Magoli Mengi)"
        elif under_pct > 65.0:
            advice = "🔒 UNDER 2.5 (Magoli Machache)"
            
        results.append({
            "home": home_name,
            "away": away_name,
            "home_xg": round(home_exp_goals, 2),
            "away_xg": round(away_exp_goals, 2),
            "under_25": round(under_pct, 1),
            "over_25": round(over_pct, 1),
            "advice": advice
        })
        
    return jsonify({"status": "success", "matches": results})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)