import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://euroquant_user:euroquant_password@db:5432/euroquant_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")

# Loop Settings
RUN_ONCE_AND_LOOP = os.getenv("RUN_ONCE_AND_LOOP", "true").lower() == "true"
LOOP_INTERVAL_HOURS = float(os.getenv("LOOP_INTERVAL_HOURS", "2"))

# Volatility warning threshold
V2TX_THRESHOLD = 30.0

# European and Global Indices to track
INDICES = {
    "^STOXX": "STOXX Europe 600",
    "^GDAXI": "DAX 40",
    "^FCHI": "CAC 40",
    "FTSEMIB.MI": "FTSE MIB",
    "^IBEX": "IBEX 35",
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ Composite",
    "^N225": "Nikkei 225",
    "^HSI": "Hang Seng Index"
}

# Source trust scores (Professional Enhancement #2)
# Any source not listed here will fallback to a default trust score of 0.60
SOURCE_TRUST_SCORES = {
    "Financial Times": 0.95,
    "Reuters Business": 0.90,
    "Bloomberg Europe": 0.90,
    "Les Echos Un": 0.90,
    "Handelsblatt": 0.90,
    "Il Sole 24 Ore Finanza": 0.90,
    "Milano Finanza Mercati": 0.90,
    "Expansión": 0.90,
    "Cinco Días": 0.85,
    "El Economista": 0.85,
    "FAZ Wirtschaft": 0.85,
    "Wirtschaftswoche": 0.85,
    "Börsen-Zeitung": 0.85,
    "La Tribune Eco": 0.85,
    "Le Monde Economie": 0.85,
    "The Economist Business": 0.90,
    "ANSA Economia": 0.80,
    "Le Figaro Economie": 0.80,
    "Der Spiegel Wirtschaft": 0.80,
    "Süddeutsche Wirtschaft": 0.80,
    "El País Economia": 0.80,
    "El Mundo Economia": 0.80,
    "Corriere Economia": 0.80,
    "La Repubblica Economia": 0.80,
    "Tagesschau Wirtschaft": 0.80,
    "Agefi": 0.80,
    "The Times Business": 0.80,
    "The Guardian Business": 0.80,
    "BBC Business": 0.80,
    "Investir Les Echos": 0.80,
    # USA
    "CNBC Finance": 0.90,
    "Bloomberg Markets": 0.90,
    "WSJ Markets": 0.90,
    "MarketWatch Market": 0.85,
    "Yahoo Finance": 0.80,
    # Asia
    "Nikkei Asia": 0.85,
    "SCMP Business": 0.80,
    "Caixin Global": 0.80,
    "Channel NewsAsia Business": 0.80
}
