#!/bin/bash
# Seed the persistent volume with database files on first deploy.
# Check for a known file (hedge_funds.csv) rather than emptiness,
# since Railway volumes may contain internal metadata even when fresh.
if [ ! -f /app/database/hedge_funds.csv ]; then
    echo "📦 Seeding database volume with initial data..."
    cp -r /app/database-seed/* /app/database/
    echo "✅ Database seeded."
else
    echo "✅ Database volume already populated."
fi

# Generate .env file from Railway environment variables if it doesn't exist.
# The app reads API keys from the .env file on disk, not process env vars.
if [ ! -f /app/.env ]; then
    echo "📝 Generating .env from environment variables..."
    env_file="/app/.env"
    [ -n "$FINNHUB_API_KEY" ]    && echo "FINNHUB_API_KEY=$FINNHUB_API_KEY" >> "$env_file"
    [ -n "$GITHUB_TOKEN" ]       && echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> "$env_file"
    [ -n "$GOOGLE_API_KEY" ]     && echo "GOOGLE_API_KEY=$GOOGLE_API_KEY" >> "$env_file"
    [ -n "$GROQ_API_KEY" ]       && echo "GROQ_API_KEY=$GROQ_API_KEY" >> "$env_file"
    [ -n "$HF_TOKEN" ]           && echo "HF_TOKEN=$HF_TOKEN" >> "$env_file"
    [ -n "$OPENROUTER_API_KEY" ] && echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" >> "$env_file"
    echo "✅ .env file created."
else
    echo "✅ .env file already exists."
fi

exec "$@"
