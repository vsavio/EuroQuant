CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    telegram_bot_token VARCHAR(255) DEFAULT '',
    telegram_chat_id VARCHAR(50) DEFAULT '',
    discord_webhook_url TEXT DEFAULT '',
    CONSTRAINT single_row CHECK (id = 1)
);
INSERT INTO system_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Audit log: tracks all security-critical and administrative actions
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details JSONB DEFAULT '{}',
    ip_address VARCHAR(50) DEFAULT 'unknown',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_username ON audit_log (username);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log (action);


CREATE TABLE IF NOT EXISTS companies (
    ticker VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50) NOT NULL,
    sector VARCHAR(50) NOT NULL,
    industry VARCHAR(100),
    trust_score NUMERIC(3, 2) DEFAULT 0.60
);

CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) REFERENCES companies(ticker) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open NUMERIC(15, 4),
    high NUMERIC(15, 4),
    low NUMERIC(15, 4),
    close NUMERIC(15, 4),
    volume BIGINT,
    rsi NUMERIC(8, 4),
    macd NUMERIC(15, 4),
    macd_signal NUMERIC(15, 4),
    sma_20 NUMERIC(15, 4),
    sma_50 NUMERIC(15, 4),
    sma_200 NUMERIC(15, 4),
    UNIQUE(ticker, timestamp)
);

CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT UNIQUE NOT NULL,
    source VARCHAR(100) NOT NULL,
    published_date TIMESTAMP WITH TIME ZONE NOT NULL,
    country VARCHAR(50) NOT NULL,
    sentiment_score NUMERIC(5, 4),
    sentiment_label VARCHAR(20),
    processed BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS news_company_mappings (
    article_id INTEGER REFERENCES news_articles(id) ON DELETE CASCADE,
    company_ticker VARCHAR(20) REFERENCES companies(ticker) ON DELETE CASCADE,
    PRIMARY KEY (article_id, company_ticker)
);

CREATE TABLE IF NOT EXISTS recommendations (
    ticker VARCHAR(20) PRIMARY KEY REFERENCES companies(ticker) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    signal VARCHAR(20) NOT NULL, -- STRONG BUY, BUY, HOLD, SELL, STRONG SELL
    sentiment_score NUMERIC(5, 4),
    price_change_24h NUMERIC(15, 4),
    reason_macro TEXT,
    reason_micro TEXT,
    reason_technical TEXT,
    full_reason TEXT
);

CREATE TABLE IF NOT EXISTS rss_feeds (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    feed_url TEXT UNIQUE NOT NULL,
    country VARCHAR(50) NOT NULL,
    trust_score NUMERIC(3, 2) NOT NULL DEFAULT 0.60
);

-- Seed companies data
INSERT INTO companies (ticker, name, country, sector, industry, trust_score) VALUES
-- Indices
('^STOXX', 'STOXX Europe 600', 'Europe', 'Index', 'Index', 1.00),
('^GDAXI', 'DAX 40', 'Germany', 'Index', 'Index', 1.00),
('^FCHI', 'CAC 40', 'France', 'Index', 'Index', 1.00),
('FTSEMIB.MI', 'FTSE MIB', 'Italy', 'Index', 'Index', 1.00),
('^V2TX', 'VSTOXX Volatility Index', 'Europe', 'Index', 'Index', 1.00),
-- Forex Currency Pairs
('EURUSD=X', 'EUR/USD', 'Global', 'Forex', 'Currency', 1.00),
('GBPUSD=X', 'GBP/USD', 'Global', 'Forex', 'Currency', 1.00),
('EURGBP=X', 'EUR/GBP', 'Global', 'Forex', 'Currency', 1.00),
('EURJPY=X', 'EUR/JPY', 'Global', 'Forex', 'Currency', 1.00),
('EURCHF=X', 'EUR/CHF', 'Global', 'Forex', 'Currency', 1.00),
-- Italy (FTSE MIB)
('ENI.MI', 'Eni S.p.A.', 'Italy', 'Energy', 'Oil & Gas Integrated', 0.85),
('ENEL.MI', 'Enel S.p.A.', 'Italy', 'Utilities', 'Utilities - Regulated Electric', 0.80),
('ISP.MI', 'Intesa Sanpaolo S.p.A.', 'Italy', 'Financial Services', 'Banks - Regional', 0.85),
('UCG.MI', 'UniCredit S.p.A.', 'Italy', 'Financial Services', 'Banks - Regional', 0.85),
('STLAM.MI', 'Stellantis N.V.', 'Italy', 'Consumer Cyclical', 'Auto Manufacturers', 0.80),
('RACE.MI', 'Ferrari N.V.', 'Italy', 'Consumer Cyclical', 'Auto Manufacturers', 0.90),
-- France (CAC 40)
('TTE.PA', 'TotalEnergies SE', 'France', 'Energy', 'Oil & Gas Integrated', 0.85),
('MC.PA', 'LVMH Moët Hennessy Louis Vuitton SE', 'France', 'Consumer Cyclical', 'Luxury Goods', 0.90),
('SAN.PA', 'Sanofi', 'France', 'Healthcare', 'Drug Manufacturers - General', 0.85),
('OR.PA', 'L''Oréal S.A.', 'France', 'Consumer Defensive', 'Household & Personal Products', 0.85),
('SU.PA', 'Schneider Electric SE', 'France', 'Industrials', 'Specialty Industrial Machinery', 0.85),
('BNP.PA', 'BNP Paribas S.A.', 'France', 'Financial Services', 'Banks - Diversified', 0.85),
-- Germany (DAX 40)
('SAP.DE', 'SAP SE', 'Germany', 'Technology', 'Software - Application', 0.90),
('SIE.DE', 'Siemens AG', 'Germany', 'Industrials', 'Specialty Industrial Machinery', 0.85),
('ALV.DE', 'Allianz SE', 'Germany', 'Financial Services', 'Insurance - Diversified', 0.85),
('DTE.DE', 'Deutsche Telekom AG', 'Germany', 'Communication Services', 'Telecom Services', 0.80),
('BAS.DE', 'BASF SE', 'Germany', 'Basic Materials', 'Chemicals', 0.80),
('VOW3.DE', 'Volkswagen AG', 'Germany', 'Consumer Cyclical', 'Auto Manufacturers', 0.80),
-- Spain (IBEX 35)
('IBE.MC', 'Iberdrola, S.A.', 'Spain', 'Utilities', 'Utilities - Regulated Electric', 0.80),
('SAN.MC', 'Banco Santander, S.A.', 'Spain', 'Financial Services', 'Banks - Diversified', 0.80),
('BBVA.MC', 'Banco Bilbao Vizcaya Argentaria, S.A.', 'Spain', 'Financial Services', 'Banks - Diversified', 0.80),
('TEF.MC', 'Telefónica, S.A.', 'Spain', 'Communication Services', 'Telecom Services', 0.75),
('ITX.MC', 'Industria de Diseño Textil, S.A. (Inditex)', 'Spain', 'Consumer Cyclical', 'Apparel Retail', 0.85),
('REP.MC', 'Repsol, S.A.', 'Spain', 'Energy', 'Oil & Gas Integrated', 0.75),
-- United Kingdom (FTSE 100)
('SHEL.L', 'Shell plc', 'United Kingdom', 'Energy', 'Oil & Gas Integrated', 0.90),
('AZN.L', 'AstraZeneca plc', 'United Kingdom', 'Healthcare', 'Drug Manufacturers - General', 0.90),
('HSBA.L', 'HSBC Holdings plc', 'United Kingdom', 'Financial Services', 'Banks - Diversified', 0.90),
('ULVR.L', 'Unilever PLC', 'United Kingdom', 'Consumer Defensive', 'Household & Personal Products', 0.85),
('BP.L', 'BP p.l.c.', 'United Kingdom', 'Energy', 'Oil & Gas Integrated', 0.85),
('GSK.L', 'GSK plc', 'United Kingdom', 'Healthcare', 'Drug Manufacturers - General', 0.85)
ON CONFLICT (ticker) DO UPDATE SET
    name = EXCLUDED.name,
    country = EXCLUDED.country,
    sector = EXCLUDED.sector,
    industry = EXCLUDED.industry,
    trust_score = EXCLUDED.trust_score;

-- Seed RSS feeds (10 per country)
INSERT INTO rss_feeds (source_name, feed_url, country, trust_score) VALUES
-- Italy
('Il Sole 24 Ore Finanza', 'https://www.ilsole24ore.com/rss/finanza.xml', 'Italy', 0.90),
('Milano Finanza Mercati', 'https://www.milanofinanza.it/rss/finanza-mercati', 'Italy', 0.90),
('La Repubblica Economia', 'https://www.repubblica.it/rss/economia/rss2.0.xml', 'Italy', 0.80),
('Corriere Economia', 'http://xml2.corriereobjects.it/rss/economia.xml', 'Italy', 0.80),
('ANSA Economia', 'http://www.ansa.it/sito/notizie/economia/economia_rss.xml', 'Italy', 0.80),
('Wall Street Italia', 'https://www.wallstreetitalia.com/feed/', 'Italy', 0.70),
('Investire Oggi', 'https://www.investireoggi.it/economia/feed/', 'Italy', 0.65),
('Teleborsa', 'https://www.teleborsa.it/Rss/RssNews.xml', 'Italy', 0.75),
('Finanza Online', 'https://www.finanzaonline.com/feed', 'Italy', 0.70),
('QuiFinanza', 'https://quifinanza.it/feed/', 'Italy', 0.70),
-- France
('Les Echos Un', 'https://www.lesechos.fr/rss/rss_la_une.xml', 'France', 0.90),
('La Tribune Eco', 'https://www.latribune.fr/rss/la-tribune-de-l-eco.xml', 'France', 0.85),
('Le Monde Economie', 'https://www.lemonde.fr/economie/rss_full.xml', 'France', 0.85),
('Le Figaro Economie', 'https://www.lefigaro.fr/rss/figaro_economie.xml', 'France', 0.80),
('BFM Business', 'https://www.bfmtv.com/rss/economie/', 'France', 0.80),
('Capital', 'https://www.capital.fr/rss/economie.xml', 'France', 0.75),
('L''Usine Nouvelle', 'https://www.usinenouvelle.com/rss/', 'France', 0.75),
('Investir Les Echos', 'https://investir.lesechos.fr/rss/rss_actualites.xml', 'France', 0.80),
('Challenges Economie', 'https://www.challenges.fr/economie/rss.xml', 'France', 0.75),
('Agefi', 'https://www.agefi.fr/rss', 'France', 0.80),
-- Germany
('Handelsblatt', 'https://www.handelsblatt.com/contentexport/feed/top-themen/', 'Germany', 0.90),
('FAZ Wirtschaft', 'https://www.faz.net/rss/aktuell/wirtschaft/', 'Germany', 0.85),
('Wirtschaftswoche', 'https://www.wiwo.de/contentexport/feed/top-themen/', 'Germany', 0.85),
('Der Spiegel Wirtschaft', 'https://www.spiegel.de/wirtschaft/index.rss', 'Germany', 0.80),
('Süddeutsche Wirtschaft', 'https://rss.sueddeutsche.de/rss/Wirtschaft', 'Germany', 0.80),
('Börsen-Zeitung', 'https://www.boersen-zeitung.de/rss.xml', 'Germany', 0.85),
('Manager Magazin', 'https://www.manager-magazin.de/index.rss', 'Germany', 0.80),
('Finanzen.net', 'https://www.finanzen.net/rss/finanzen-news', 'Germany', 0.75),
('OnVista', 'https://www.onvista.de/news/rss', 'Germany', 0.70),
('Tagesschau Wirtschaft', 'https://www.tagesschau.de/wirtschaft/index.rss', 'Germany', 0.80),
-- Spain
('Expansión', 'https://www.expansion.com/rss/portada.xml', 'Spain', 0.90),
('Cinco Días', 'https://cincodias.elpais.com/rss/cincodias/portada.xml', 'Spain', 0.85),
('El Economista', 'https://www.eleconomista.es/rss/rss-portada.php', 'Spain', 0.85),
('Bolsamanía', 'https://www.bolsamania.com/rss/portada.xml', 'Spain', 0.75),
('El País Economia', 'https://elpais.com/rss/economia.xml', 'Spain', 0.80),
('El Mundo Economia', 'https://e00-elmundo.uecdn.es/elmundo/rss/economia.xml', 'Spain', 0.80),
('Invertia', 'https://www.elespanol.com/invertia/rss/', 'Spain', 0.75),
('Finanzas.com', 'https://www.finanzas.com/rss/', 'Spain', 0.70),
('Capital Radio', 'https://www.capitalradio.es/feed/', 'Spain', 0.70),
('Estrategias de Inversión', 'https://www.estrategiasdeinversion.com/rss/noticias/', 'Spain', 0.75),
-- United Kingdom
('Financial Times', 'https://www.ft.com/news-feed.rss', 'United Kingdom', 0.95),
('Reuters Business', 'https://www.reutersagency.com/feed/', 'United Kingdom', 0.90),
('Bloomberg Europe', 'https://www.bloomberg.com/feeds/bpol/europe.xml', 'United Kingdom', 0.90),
('The Economist Business', 'https://www.economist.com/business/rss.xml', 'United Kingdom', 0.90),
('City A.M.', 'https://www.cityam.com/feed/', 'United Kingdom', 0.75),
('The Telegraph Business', 'https://www.telegraph.co.uk/business/rss.xml', 'United Kingdom', 0.80),
('The Times Business', 'https://www.thetimes.co.uk/section/business/rss', 'United Kingdom', 0.80),
('The Guardian Business', 'https://www.theguardian.com/business/rss', 'United Kingdom', 0.80),
('BBC Business', 'http://feeds.bbci.co.uk/news/business/rss.xml', 'United Kingdom', 0.80),
('Evening Standard Business', 'https://www.standard.co.uk/business/rss', 'United Kingdom', 0.75)
ON CONFLICT (feed_url) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    country = EXCLUDED.country,
    trust_score = EXCLUDED.trust_score;

-- Seed US and Asian companies data
INSERT INTO companies (ticker, name, country, sector, industry, trust_score) VALUES
-- USA
('AAPL', 'Apple Inc.', 'USA', 'Technology', 'Consumer Electronics', 0.95),
('MSFT', 'Microsoft Corporation', 'USA', 'Technology', 'Software - Infrastructure', 0.95),
('AMZN', 'Amazon.com, Inc.', 'USA', 'Consumer Cyclical', 'Internet Retail', 0.90),
('NVDA', 'NVIDIA Corporation', 'USA', 'Technology', 'Semiconductors', 0.95),
('GOOGL', 'Alphabet Inc.', 'USA', 'Technology', 'Internet Content & Information', 0.90),
('TSLA', 'Tesla, Inc.', 'USA', 'Consumer Cyclical', 'Auto Manufacturers', 0.90),
('META', 'Meta Platforms, Inc.', 'USA', 'Technology', 'Internet Content & Information', 0.85),
('JPM', 'JPMorgan Chase & Co.', 'USA', 'Financial Services', 'Banks - Diversified', 0.90),
('V', 'Visa Inc.', 'USA', 'Financial Services', 'Credit Services', 0.90),
('LLY', 'Eli Lilly and Company', 'USA', 'Healthcare', 'Drug Manufacturers - General', 0.90),
-- Japan
('7203.T', 'Toyota Motor Corporation', 'Japan', 'Consumer Cyclical', 'Auto Manufacturers', 0.85),
('9984.T', 'SoftBank Group Corp.', 'Japan', 'Technology', 'Telecom Services', 0.80),
('6758.T', 'Sony Group Corporation', 'Japan', 'Consumer Cyclical', 'Consumer Electronics', 0.85),
-- Hong Kong
('0700.HK', 'Tencent Holdings Limited', 'Hong Kong', 'Technology', 'Internet Content & Information', 0.85),
('9988.HK', 'Alibaba Group Holding Limited', 'Hong Kong', 'Consumer Cyclical', 'Internet Retail', 0.80),
('1211.HK', 'BYD Company Limited', 'Hong Kong', 'Consumer Cyclical', 'Auto Manufacturers', 0.80),
-- Taiwan
('2330.TW', 'Taiwan Semiconductor Manufacturing Co.', 'Taiwan', 'Technology', 'Semiconductors', 0.95),
-- South Korea
('005930.KS', 'Samsung Electronics Co., Ltd.', 'South Korea', 'Technology', 'Consumer Electronics', 0.90),
-- Crypto
('BTC-USD', 'Bitcoin', 'Crypto', 'Crypto', 'Cryptocurrency', 0.95),
('ETH-USD', 'Ethereum', 'Crypto', 'Crypto', 'Cryptocurrency', 0.90),
('XRP-USD', 'Ripple', 'Crypto', 'Crypto', 'Cryptocurrency', 0.85),
('SOL-USD', 'Solana', 'Crypto', 'Crypto', 'Cryptocurrency', 0.85),
('ADA-USD', 'Cardano', 'Crypto', 'Crypto', 'Cryptocurrency', 0.80),
('DOT-USD', 'Polkadot', 'Crypto', 'Crypto', 'Cryptocurrency', 0.80)
ON CONFLICT (ticker) DO UPDATE SET
    name = EXCLUDED.name,
    country = EXCLUDED.country,
    sector = EXCLUDED.sector,
    industry = EXCLUDED.industry,
    trust_score = EXCLUDED.trust_score;

-- Seed US and Asian RSS feeds
INSERT INTO rss_feeds (source_name, feed_url, country, trust_score) VALUES
-- USA
('CNBC Finance', 'https://search.cnbc.com/rs/search/all/view.xml?partnerId=2000&keywords=finance', 'USA', 0.90),
('Bloomberg Markets', 'https://www.bloomberg.com/feeds/bpol/markets.xml', 'USA', 0.90),
('WSJ Markets', 'https://feeds.a.dj.com/rss/RSSMarketsMain.xml', 'USA', 0.90),
('MarketWatch Market', 'https://feeds.content.marketwatch.com/marketwatch/rss/marketalerts', 'USA', 0.85),
('Yahoo Finance', 'https://finance.yahoo.com/news/rssindex', 'USA', 0.80),
-- Asia
('Nikkei Asia', 'https://asia.nikkei.com/rss/feed/nar', 'Japan', 0.85),
('SCMP Business', 'https://www.scmp.com/rss/92/feed.xml', 'Hong Kong', 0.80),
('Caixin Global', 'https://www.caixinglobal.com/rss/', 'China', 0.80),
('Channel NewsAsia Business', 'https://www.channelnewsasia.com/api/v1/rss-outbound-feed?category=6911', 'Singapore', 0.80),
-- Crypto
('CoinDesk Feed', 'https://www.coindesk.com/arc/outboundfeeds/rss/', 'Crypto', 0.85),
('Cointelegraph Feed', 'https://cointelegraph.com/rss', 'Crypto', 0.85),
('Decrypt Feed', 'https://decrypt.co/feed', 'Crypto', 0.80)
ON CONFLICT (feed_url) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    country = EXCLUDED.country,
    trust_score = EXCLUDED.trust_score;

-- ML model metrics table to track performance statistics and check drift
CREATE TABLE IF NOT EXISTS ml_model_metrics (
    ticker VARCHAR(20) PRIMARY KEY REFERENCES companies(ticker) ON DELETE CASCADE,
    last_trained TIMESTAMPTZ DEFAULT NOW(),
    accuracy NUMERIC(5, 4),
    precision NUMERIC(5, 4),
    recall NUMERIC(5, 4),
    f1_score NUMERIC(5, 4),
    total_samples INTEGER,
    features_used JSONB DEFAULT '[]'
);

