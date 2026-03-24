import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import axios from "axios";
import { createClient } from "@supabase/supabase-js";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import { FootyEdgePredictor } from "./src/lib/predictor.ts";
import { FootyEdgeBranding } from "./src/lib/branding.ts";
import { FootballDataService } from "./src/lib/footballData.ts";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let supabaseClient: any = null;
function getSupabase() {
  if (!supabaseClient) {
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_KEY;
    if (!url || !key) {
      throw new Error("Supabase environment variables (SUPABASE_URL, SUPABASE_SERVICE_KEY) are missing. Please set them in the Settings menu.");
    }
    supabaseClient = createClient(url, key);
  }
  return supabaseClient;
}

const predictor = new FootyEdgePredictor();

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(cors());
  app.use(express.json());

  // API Routes
  app.get("/api", (req, res) => {
    res.json({
      name: FootyEdgeBranding.PRODUCT_NAME,
      version: "1.0.0",
      powered_by: FootyEdgeBranding.COMPANY_NAME,
      architecture: {
        type: "Multi-Agent AI",
        agents: FootyEdgeBranding.AGENTS.map(a => `${a.name} (${a.role})`),
        database: "PostgreSQL",
        deployment: "Cloud Native"
      },
      status: "operational"
    });
  });

  app.get("/api/branding", (req, res) => {
    res.json({
      name: FootyEdgeBranding.PRODUCT_NAME,
      version: "1.0.0",
      powered_by: FootyEdgeBranding.COMPANY_NAME,
      architecture: {
        type: "Multi-Agent AI",
        agents: FootyEdgeBranding.AGENTS.map(a => `${a.name} (${a.role})`),
        database: "PostgreSQL",
        deployment: "Cloud Native"
      },
      status: "operational"
    });
  });

  app.get("/api/health", (req, res) => {
    res.json({ 
      status: "running",
      powered_by: FootyEdgeBranding.COMPANY_NAME,
      database: process.env.SUPABASE_URL ? "configured" : "missing",
      rapidapi: process.env.RAPIDAPI_KEY ? "configured" : "missing",
      timestamp: new Date().toISOString()
    });
  });

  app.get("/api/matches/today", async (req, res) => {
    try {
      const matches = await FootballDataService.getTodaysMatches();
      res.json(matches);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.get("/api/matches/:id/odds", async (req, res) => {
    const { id } = req.params;
    try {
      const baseOdds = await FootballDataService.getOdds(id);
      
      // Market Expansion: Simulate odds from multiple bookmakers
      const multiBookieOdds = {
        bet9ja: { ...baseOdds, booking_prefix: 'B9JA-' },
        sportybet: { 
          home_win: (baseOdds.home_win * 0.98).toFixed(2), 
          draw: (baseOdds.draw * 1.02).toFixed(2), 
          away_win: (baseOdds.away_win * 1.01).toFixed(2),
          booking_prefix: 'SB-'
        },
        '1xbet': { 
          home_win: (baseOdds.home_win * 1.03).toFixed(2), 
          draw: (baseOdds.draw * 0.97).toFixed(2), 
          away_win: (baseOdds.away_win * 0.99).toFixed(2),
          booking_prefix: '1X-'
        }
      };
      
      res.json(multiBookieOdds);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.post("/api/telegram/broadcast", async (req, res) => {
    const { prediction, valueBet, isPremium } = req.body;
    const token = process.env.TELEGRAM_BOT_TOKEN;
    const chatId = process.env.TELEGRAM_CHAT_ID;

    if (!token || !chatId) {
      return res.status(400).json({ error: "Telegram bot not configured" });
    }

    const header = isPremium ? "💎 *ORACLE69 PREMIUM SIGNAL* 💎" : "🆓 *ORACLE69 FREE SIGNAL* 🆓";
    const matchInfo = `⚽️ *Match:* ${prediction.home_team} vs ${prediction.away_team}`;
    const selectionInfo = `🎯 *Selection:* ${valueBet.selection}`;
    const oddsInfo = `📈 *Odds:* ${valueBet.odds.toFixed(2)}`;
    const confidenceInfo = `🔥 *Confidence:* ${(prediction.confidence * 100).toFixed(0)}%`;
    const evInfo = `💰 *Expected Value:* +${(valueBet.ev * 100).toFixed(1)}%`;
    
    const footer = isPremium 
      ? "\n🚀 _Stake responsibly. Premium signals have 85%+ historical accuracy._"
      : "\n👉 *Join Premium for 10+ daily high-confidence signals:* [Upgrade Now](https://oracle69.systems/premium)";

    const message = `${header}\n\n${matchInfo}\n${selectionInfo}\n${oddsInfo}\n${confidenceInfo}\n${evInfo}\n${footer}`;

    try {
      await axios.post(`https://api.telegram.org/bot${token}/sendMessage`, {
        chat_id: chatId,
        text: message,
        parse_mode: 'Markdown',
        disable_web_page_preview: true
      });
      res.json({ success: true });
    } catch (error: any) {
      console.error("Telegram error:", error.response?.data || error.message);
      res.status(500).json({ error: "Failed to send Telegram message" });
    }
  });

  app.post("/api/premium/subscribe", async (req, res) => {
    const { userId, plan } = req.body;
    // In a real app, this would integrate with Stripe/Paystack/Flutterwave
    // For now, we'll mock a successful subscription
    try {
      const supabase = getSupabase();
      const { error } = await supabase
        .from("profiles")
        .update({ 
          is_premium: true, 
          premium_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString() 
        })
        .eq("id", userId);

      if (error) throw error;
      res.json({ success: true, message: `Subscribed to ${plan} plan!` });
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.post("/api/acca/generate", async (req, res) => {
    const { selections } = req.body; // Array of { matchId, market, odds }
    
    try {
      const totalOdds = selections.reduce((acc: number, s: any) => acc * s.odds, 1).toFixed(2);
      const bookingCode = `ACCA-${Math.random().toString(36).substring(2, 10).toUpperCase()}`;
      
      res.json({
        bookingCode,
        totalOdds,
        selectionsCount: selections.length
      });
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.post("/api/bets/record", async (req, res) => {
    const { user_id, match_id, prediction_id, market, selection, odds, stake } = req.body;
    
    try {
      const supabase = getSupabase();
      const potential_win = stake * odds;
      
      const { data, error } = await supabase
        .from("user_bets")
        .insert({
          user_id,
          match_id,
          prediction_id,
          market,
          selection,
          odds,
          stake,
          potential_win,
          status: 'pending'
        })
        .select()
        .single();

      if (error) throw error;
      res.json(data);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.get("/api/bets/user/:userId", async (req, res) => {
    const { userId } = req.params;
    try {
      const supabase = getSupabase();
      const { data, error } = await supabase
        .from("user_bets")
        .select("*")
        .eq("user_id", userId)
        .order("created_at", { ascending: false });
      
      if (error) throw error;
      res.json(data);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.post("/api/predict", async (req, res) => {
    const { home_team_id, away_team_id } = req.body;
    
    try {
      const supabase = getSupabase();
      // Fetch teams from Supabase
      const { data: teams, error: teamsError } = await supabase
        .from("teams")
        .select("*")
        .in("id", [home_team_id, away_team_id]);

      if (teamsError || !teams || teams.length < 2) {
        return res.status(404).json({ error: "Teams not found" });
      }

      const homeTeam = teams.find(t => t.id === home_team_id);
      const awayTeam = teams.find(t => t.id === away_team_id);

      const prediction = predictor.predictMatch(homeTeam, awayTeam);
      
      // Mark as premium if confidence is high (> 80%)
      const isPremium = prediction.confidence > 0.80;
      prediction.is_premium = isPremium;

      // Mock odds for now
      const mockOdds = {
        home_win: 1.85,
        draw: 3.40,
        away_win: 4.20,
        over_2_5: 1.95,
        under_2_5: 1.85,
        btts_yes: 1.75
      };
      
      const valueBets = predictor.findValueBets(prediction, mockOdds);

      // Save to Supabase
      const { data: predData, error: predError } = await supabase
        .from("predictions")
        .insert({
          home_team: prediction.home_team,
          away_team: prediction.away_team,
          home_prob: prediction.home_prob,
          draw_prob: prediction.draw_prob,
          away_prob: prediction.away_prob,
          home_xg: prediction.home_xg,
          away_xg: prediction.away_xg,
          over_2_5_prob: prediction.over_2_5_prob,
          under_2_5_prob: prediction.under_2_5_prob,
          btts_prob: prediction.btts_prob,
          is_premium: prediction.is_premium,
          confidence: prediction.confidence,
          best_bet_market: valueBets[0]?.market,
          best_bet_selection: valueBets[0]?.selection,
          best_bet_odds: valueBets[0]?.odds,
          best_bet_ev: valueBets[0]?.ev
        })
        .select()
        .single();

      if (predError) throw predError;

      if (valueBets.length > 0) {
        await supabase.from("value_bets").insert(
          valueBets.map(bet => ({
            prediction_id: predData.id,
            match: bet.match,
            market: bet.market,
            selection: bet.selection,
            odds: bet.odds,
            our_probability: bet.our_probability,
            ev: bet.ev,
            kelly_percentage: bet.kelly,
            recommended_stake: bet.recommended_stake
          }))
        );
      }

      res.json({ prediction, value_bets: valueBets });
    } catch (error: any) {
      console.error("Prediction error:", error);
      res.status(500).json({ error: error.message });
    }
  });

  app.get("/api/predictions", async (req, res) => {
    const limit = parseInt(req.query.limit as string) || 10;
    try {
      const supabase = getSupabase();
      const { data, error } = await supabase
        .from("predictions")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit);
      
      if (error) return res.status(500).json({ error: error.message });
      res.json(data);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.get("/api/value-bets", async (req, res) => {
    const status = req.query.status as string || "active";
    try {
      const supabase = getSupabase();
      let query = supabase
        .from("value_bets")
        .select("*")
        .order("ev", { ascending: false });
      
      if (status !== "all") {
        query = query.eq("status", status);
      }
      
      const { data, error } = await query;
      
      if (error) return res.status(500).json({ error: error.message });
      res.json(data);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.patch("/api/value-bets/:id", async (req, res) => {
    const { id } = req.params;
    const { status } = req.body;

    if (!["active", "won", "lost"].includes(status)) {
      return res.status(400).json({ error: "Invalid status" });
    }

    try {
      const supabase = getSupabase();
      const { data, error } = await supabase
        .from("value_bets")
        .update({ status })
        .eq("id", id)
        .select()
        .single();

      if (error) return res.status(500).json({ error: error.message });
      res.json(data);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  app.get("/api/players/search", async (req, res) => {
    const { query } = req.query;
    if (!query) return res.status(400).json({ error: "Query parameter is required" });

    try {
      const response = await axios.get(`https://free-api-live-football-data.p.rapidapi.com/football-players-search?search=${query}`, {
        headers: {
          'x-rapidapi-host': process.env.RAPIDAPI_HOST || 'free-api-live-football-data.p.rapidapi.com',
          'x-rapidapi-key': process.env.RAPIDAPI_KEY
        }
      });
      res.json(response.data);
    } catch (error: any) {
      console.error("RapidAPI error:", error.response?.data || error.message);
      res.status(error.response?.status || 500).json({ error: "Failed to fetch players" });
    }
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
    
    // SPA fallback for development
    app.use("*", (req, res, next) => {
      if (req.originalUrl.startsWith("/api")) {
        return next();
      }
      // Vite handles the index.html serving in middlewareMode: true
      next();
    });
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
