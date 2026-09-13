# RAASTA AI — Final Product Notes

## Implemented
- Manual start and destination input
- Arbitrary Lahore landmark lookup without API keys
- Exact-stop matching from the RAASTA AI dataset
- Ambiguous stop-name resolution prefers major hubs/Metro stops (for example, “Shahdara” → “Shahdara Metro Bus Station”)
- Recognized exact stops are preserved through routing instead of being re-guessed from coordinates
- Nearest **usable** stop selection (tries multiple nearby stops instead of failing on a disconnected closest stop)
- Public-transport route calculation from verified structured data
- Boarding, drop-off and transfer instructions
- Walking distance/time estimates to/from transit stops
- Fastest, cheapest, fewest-change and least-walking ranking
- One clear route priority at a time
- Alternative route statistics
- Start and destination pins only on the map
- Local semantic AI/RAG integrated into the live app
- Grounded AI explanation that cannot change or invent the computed route
- Error handling for incomplete, unrecognized and unroutable journeys
- Simplified final header: RAASTA AI branding + light/dark theme toggle only
- Removed How it works, About, language switcher, and technical captions below the map/AI explanation

## Intentionally excluded
- Voice input/output (removed by project decision)
- Real-time bus tracking
- Traffic prediction
- Accounts/history
- Push notifications
- Payments/ticketing
- API-key-based Google Maps/Groq services
