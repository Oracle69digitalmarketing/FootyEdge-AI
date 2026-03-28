# FootyEdge AI

![FootyEdge AI Logo](src/assets/logo.png)

## Unleash Your Betting Edge with AI-Powered Football Analytics

FootyEdge AI is a cutting-edge platform designed to revolutionize your football betting strategy. Leveraging a sophisticated multi-agent AI architecture, real-time data integration, and advanced statistical models, we provide unparalleled insights to help you identify value bets and optimize your returns.

---

## ✨ Features

*   **Multi-Agent AI Engine:** A powerful system comprising specialized AI agents working in concert to analyze matches and betting markets.
*   **Real-time Match Intelligence:** Generate deep analytical insights for any fixture, including win probabilities, expected goals (xG), and key statistical breakdowns.
*   **Live Value Bet Scanner:** Automatically identify betting inefficiencies across major bookmakers with positive Expected Value (EV).
*   **Player & Team Search:** Access comprehensive historical and current statistics for football teams and players globally.
*   **Acca Builder:** Construct optimized accumulator bets with dynamic odds calculation and booking code generation.
*   **Personalized Portfolio Tracking:** Monitor your betting history, track active bets, analyze win rates, and manage your bankroll.
*   **Premium Hub:** Unlock exclusive, high-confidence signals, advanced performance metrics, and premium Telegram alerts for elite members.
*   **Admin Control Panel:** (For administrators) Monitor system health, user statistics, and manage platform operations.
*   **Secure Authentication:** User authentication and data management powered by Supabase.

---

## 🚀 Technologies Used

**Frontend:**
*   **React:** A JavaScript library for building user interfaces.
*   **TypeScript:** A typed superset of JavaScript that compiles to plain JavaScript.
*   **Tailwind CSS:** A utility-first CSS framework for rapidly building custom designs.
*   **Vite:** A fast frontend build tool.

**Backend:**
*   **FastAPI:** A modern, fast (high-performance) web framework for building APIs with Python 3.7+.
*   **Python:** The primary programming language for backend logic and AI models.
*   **Uvicorn:** An ASGI web server, used to serve the FastAPI application.

**Database:**
*   **PostgreSQL:** A powerful, open-source object-relational database system.
*   **Supabase:** An open-source Firebase alternative providing PostgreSQL database, Authentication, instant APIs, and Realtime subscriptions.

**Data & APIs:**
*   **RapidAPI (api-football-v1):** External API for comprehensive football data (fixtures, odds, statistics, players).

---

## 🛠️ Getting Started

Follow these instructions to set up and run the FootyEdge AI project on your local machine.

### Prerequisites

*   Node.js (LTS version recommended)
*   Python 3.8+
*   Docker (Optional, for easy PostgreSQL/Supabase setup)
*   RapidAPI Key (for API-Football v1)
*   Supabase Project (URL and Anon Key)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/username/FootyEdge-AI.git
    cd FootyEdge-AI
    ```

2.  **Backend Setup:**
    *   Create a Python virtual environment and activate it:
        ```bash
        python3 -m venv venv
        source venv/bin/activate  # On Windows use `venv\Scripts\activate`
        ```
    *   Install Python dependencies:
        ```bash
        pip install -r requirements.txt
        ```
    *   Create a `.env` file in the root directory and add your environment variables:
        ```
        RAPIDAPI_KEY="YOUR_RAPIDAPI_KEY"
        SUPABASE_URL="YOUR_SUPABASE_URL"
        SUPABASE_KEY="YOUR_SUPABASE_ANON_KEY"
        ```
        _Replace placeholders with your actual keys and URLs._

3.  **Frontend Setup:**
    *   Install Node.js dependencies:
        ```bash
        npm install
        ```
    *   The Supabase environment variables for the frontend (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) are expected to be injected by your build tool (Vite). Ensure these are configured in your `.env` file (Vite automatically picks up `VITE_` prefixed variables).
        ```
        VITE_SUPABASE_URL="YOUR_SUPABASE_URL"
        VITE_SUPABASE_ANON_KEY="YOUR_SUPABASE_ANON_KEY"
        ```

4.  **Database Setup (Supabase):**
    *   Create a new project in Supabase.
    *   Copy your Supabase Project URL and Anon Key to your `.env` file.
    *   In your Supabase project's SQL Editor, run the schema from `supabase_schema.sql` to set up the necessary tables (e.g., `teams`, `predictions`, `value_bets`, `accas`, `profiles`).
    *   Optionally, use the "Seed Database" button in the application's Intelligence Engine tab to populate some initial team data.

---

## ▶️ Running the Application

1.  **Start the Backend API:**
    Open a terminal in the project root and run:
    ```bash
    source venv/bin/activate # if not already active
    uvicorn api:app --reload
    ```
    The API will be accessible at `http://127.0.0.1:8000`.

2.  **Start the Frontend Development Server:**
    Open a *new* terminal in the project root and run:
    ```bash
    npm run dev
    ```
    The frontend application will be accessible at `http://localhost:5173` (or another port if 5173 is in use).

---

## 💡 Usage

*   **Authentication:** Sign up or log in using your email and password.
*   **Navigation:** Use the sidebar to navigate between different features:
    *   **Dashboard:** Overview of live alerts, matches, and the Intelligence Engine.
    *   **Predictions:** View recent AI-generated match predictions.
    *   **Value Bets:** Manage high Expected Value (EV) bets.
    *   **Teams / Players:** Search for detailed football data.
    *   **Acca Builder:** Create accumulator bets.
    *   **Portfolio:** Track your betting performance.
    *   **Premium Hub:** Access exclusive premium features.
    *   **Admin Panel:** (If admin) Manage platform.
    *   **Pricing:** View subscription plans.
    *   **How to Use:** Detailed guide on using the application.

*   **Generating Match Intelligence:** Navigate to the Dashboard, select home and away teams, and click "Generate Match Intelligence".
*   **Recording Accas:** Use the Acca Builder to add selections and generate booking codes. Your accas will be recorded.
*   **Telegram Integration:** Join our Telegram channel via the Dashboard for direct alerts (link in the dashboard).

For a more comprehensive guide, please refer to the "How to Use" section within the application itself.

---

## 🤝 Contributing

We welcome contributions! Please follow these steps to contribute:
1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes and commit them (`git commit -m 'feat: Add new feature'`).
4.  Push to the branch (`git push origin feature/your-feature-name`).
5.  Open a Pull Request.

---

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details. <!-- Assuming a LICENSE file exists or will be created -->

---

## 📧 Contact

For support, questions, or business inquiries, please contact us at `support@footyedge.ai`.

---

© 2026 Oracle69 Systems. All rights reserved.
