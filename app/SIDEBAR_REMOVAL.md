# Sidebar Features - v3.0 React Rebuild

## Features Restored (March 2026)

Following the v3.0 architecture rebuild from Streamlit to React + FastAPI, all features have been restored:

### Current Sidebar Components

1. **System Status** - Real-time GPU/VRAM/CPU/Temperature metrics
   - Updates every 2 seconds via JavaScript polling
   - Color-coded load bar (green → yellow → orange → red)
   - Dismissible warnings for critical thresholds
   - Independent of chat - no page refresh needed

2. **Common Questions** - Quick-access veteran FAQ dropdown
   - Organized by category
   - One-click to populate chat input

3. **Settings** - Session management
   - Recent questions count and list
   - Session context count
   - Clear session button

4. **Knowledge Base** - Database statistics
   - Page counts by source type
   - Color-coded source indicators

## Architecture Change

| Component | v2 (Streamlit) | v3 (React) |
| --- | --- | --- |
| UI Framework | Streamlit | React + Nginx |
| Status Updates | On interaction only | Every 2 seconds (polling) |
| Chat | Disrupted by refresh | Independent |
| API | Separate container | FastAPI with CORS |
