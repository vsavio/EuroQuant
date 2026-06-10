-- Create tables for EuroQuant Framework

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
    macd NUMERIC(8, 4),
    macd_signal NUMERIC(8, 4),
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
    price_change_24h NUMERIC(8, 4),
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
