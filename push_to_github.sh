#!/bin/bash

# ==============================================================================
# EuroQuant — Utility per il Commit e il Push su GitHub
# ==============================================================================
# Questo script aggiunge, committa e carica in sicurezza le modifiche su GitHub.
# NOTA: Il file di configurazione locale (.env) è escluso in automatico tramite .gitignore.
#
# Uso:
#   1. Rendi eseguibile lo script (solo la prima volta):
#      chmod +x push_to_github.sh
#
#   2. Esegui lo script passando il messaggio del commit:
#      ./push_to_github.sh "Messaggio descrittivo delle modifiche" 
# ==============================================================================

# Ferma lo script in caso di errori
set -e

# Verifica che sia stato inserito un messaggio di commit
if [ -z "$1" ]; then
    echo "❌ Errore: Messaggio di commit mancante!"
    echo "Uso corretto: ./push_to_github.sh \"il tuo messaggio di commit\""
    exit 1
fi

COMMIT_MSG="$1"

echo "🔄 1. Stato dei file modificati:"
git status -s

echo ""
echo "➕ 2. Aggiunta dei file all'area di staging (escluso .env tramite .gitignore)..."
git add .

echo ""
echo "💾 3. Creazione del commit con messaggio: \"$COMMIT_MSG\"..."
git commit -m "$COMMIT_MSG"

echo ""
echo "🚀 4. Push dei cambiamenti sul ramo 'main' di GitHub..."
git push origin main

echo ""
echo "✅ Completato con successo!"
