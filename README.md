  Full-Stack Binance Trading Bot Web Application

A full-stack trading bot platform using **FastAPI** for the backend, **Next.js** for the frontend, and Supabase for PostgreSQL and user authentication. Designed to simulate real-time trading on the Binance **Testnet**.

 Key Features
- 🔐 User Authentication** via Supabase.
- 🔑 Secure Binance API Key Management (encrypted per user).
- 💹 Trading Operations (Market, Limit, Stop orders).
- 📊 Advanced Strategies:
  - TWAP (Time-Weighted Average Price)
  - Grid Trading
- 📈 Real-Time Dashboard** for balances & strategy updates (WebSocket).
- 📚 Auto-generated API docs** with Swagger & ReDoc.

⚙️ Tech Stack

| Layer      | Tech                                   |
|------------|----------------------------------------|
| Backend    | FastAPI, SQLAlchemy, python-binance    |
| Frontend   | Next.js 13+, Tailwind CSS, Supabase JS |
| Database   | Supabase PostgreSQL                    |
| Auth       | Supabase Auth (JWT)                    |
| Realtime   | WebSocket via FastAPI                  |
| Dev Tools  | Docker, Alembic, Fernet (Encryption)   |


 📐 Architecture
mermaid
graph TD
  FE[Frontend: Next.js] -->|REST + WS| BE[Backend: FastAPI]
  BE --> DB[(Supabase PostgreSQL)]
  FE --> SupabaseAuth[Supabase Auth]

 📁 Project Structure


.
├── trading_bot_backend/
│   ├── api/
│   ├── bot/
│   ├── schemas/
│   ├── services/
│   ├── utils/
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── requirements.txt
│
├── trading_bot_frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── contexts/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── schemas/
│   ├── public/
│   ├── package.json
│   └── tailwind.config.ts
│
└── README.md
```

 ✅ Prerequisites

- Python 3.10+
- Node.js (LTS)
- Supabase Project
- Binance Testnet account
- `openssl` or Python for encryption key generation



 🚀 Setup & Installation

🔧 1. Supabase Setup

- Create a Supabase project at [supabase.com](https://supabase.com)
- Get:
  - `DATABASE_URL` (Connection string)
  - `SUPABASE_URL`, `SUPABASE_ANON_KEY`
  - `JWKS_URI`, `JWT_ISSUER`, `JWT_AUDIENCE` (Auth config)
- Enable **Email Auth** under `Authentication > Providers`



 🐍 2. Backend Setup
```bash
cd trading_bot_backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables** (via `.env` or OS env vars):
env
DATABASE_URL=...
SECRET_ENCRYPTION_KEY=...  # Use Fernet generator
SUPABASE_URL=...
SUPABASE_JWKS_URI=...
SUPABASE_JWT_ISSUER=...
SUPABASE_JWT_AUDIENCE=authenticated
🧱 Database Migrations

bash
alembic upgrade head

 ⚛️ 3. Frontend Setup

bash
cd trading_bot_frontend
npm install

Create `.env.local`:
env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/updates
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-public-key
```
 🧪 Run the App Locally

- **Backend:**  
  ```bash
  cd trading_bot_backend
  uvicorn main:app --reload --port 8000
  ```

- **Frontend:**  
  ```bash
  cd trading_bot_frontend
  npm run dev
  ```

📘 API Docs

- Swagger: [`/docs`](http://localhost:8000/docs)
- ReDoc: [`/redoc`](http://localhost:8000/redoc)

---

 🌐 Deployment Plan

| Component   | Hosting Options                           |
|-------------|--------------------------------------------|
| Supabase    | [supabase.com](https://supabase.com)       |
| Backend     | Docker → Cloud Run, Heroku, DigitalOcean   |
| Frontend    | Vercel / Netlify / Render / Fly.io         |
 🔐 Production Considerations

- Use HTTPS
- Secure secrets & JWT validation
- Set proper CORS policies
- Enable DB backups and logging



 🧠 Future Enhancements

- Save/load strategy templates
- Admin dashboard
- Notifications (e.g., Telegram, Email)
- Test coverage & CI/CD pipelines
- 2FA support via Supabase
- UI for audit logs








## License

[MIT License](LICENSE) 
