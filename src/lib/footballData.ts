import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const RAPIDAPI_KEY = process.env.RAPIDAPI_KEY;
const RAPIDAPI_HOST = process.env.RAPIDAPI_HOST || 'free-api-live-football-data.p.rapidapi.com';

export interface Fixture {
  id: string;
  homeTeam: { name: string; id: string };
  awayTeam: { name: string; id: string };
  date: string;
  status: { short: string };
  homeScore?: number;
  awayScore?: number;
}

export class FootballDataService {
  private static headers = {
    'x-rapidapi-key': RAPIDAPI_KEY,
    'x-rapidapi-host': RAPIDAPI_HOST
  };

  private static baseUrl = `https://${RAPIDAPI_HOST}`;

  static async getTodaysMatches(): Promise<Fixture[]> {
    if (!RAPIDAPI_KEY) {
      console.warn("RAPIDAPI_KEY is missing. Returning mock matches.");
      return this.getMockMatches();
    }

    try {
      const today = new Date().toISOString().split('T')[0];
      const response = await axios.get(`${this.baseUrl}/fixtures-by-date`, {
        headers: this.headers,
        params: { date: today }
      });

      return response.data.data || [];
    } catch (error) {
      console.error("Error fetching today's matches:", error);
      return this.getMockMatches();
    }
  }

  static async getTeamStats(teamId: string) {
    if (!RAPIDAPI_KEY) return null;

    try {
      const response = await axios.get(`${this.baseUrl}/team-statistics`, {
        headers: this.headers,
        params: { teamId }
      });
      return response.data.data;
    } catch (error) {
      console.error(`Error fetching stats for team ${teamId}:`, error);
      return null;
    }
  }

  static async getTeamMatches(teamId: string, limit: number = 10) {
    if (!RAPIDAPI_KEY) return [];

    try {
      const response = await axios.get(`${this.baseUrl}/fixtures-by-team`, {
        headers: this.headers,
        params: { teamId, limit }
      });
      return response.data.data || [];
    } catch (error) {
      console.error(`Error fetching matches for team ${teamId}:`, error);
      return [];
    }
  }

  static async getOdds(fixtureId: string) {
    if (!RAPIDAPI_KEY) return this.getMockOdds();

    try {
      const response = await axios.get(`${this.baseUrl}/odds`, {
        headers: this.headers,
        params: { fixtureId }
      });
      const oddsData = response.data.data || {};
      
      return {
        home_win: oddsData.homeWin || 1.9,
        draw: oddsData.draw || 3.3,
        away_win: oddsData.awayWin || 4.1,
        over_2_5: oddsData.over25 || 1.8,
        under_2_5: oddsData.under25 || 2.0,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      console.error(`Error fetching odds for fixture ${fixtureId}:`, error);
      return this.getMockOdds();
    }
  }

  private static getMockMatches(): Fixture[] {
    return [
      {
        id: "1",
        homeTeam: { name: "Manchester City", id: "10" },
        awayTeam: { name: "Arsenal", id: "11" },
        date: new Date().toISOString(),
        status: { short: "NS" }
      },
      {
        id: "2",
        homeTeam: { name: "Liverpool", id: "12" },
        awayTeam: { name: "Chelsea", id: "13" },
        date: new Date().toISOString(),
        status: { short: "NS" }
      }
    ];
  }

  private static getMockOdds() {
    return {
      home_win: 1.85,
      draw: 3.40,
      away_win: 4.20,
      over_2_5: 1.75,
      under_2_5: 2.10,
      timestamp: new Date().toISOString()
    };
  }
}
