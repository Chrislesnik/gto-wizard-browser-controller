# GTO Wizard Browser Controller

A FastAPI application that uses Playwright to control browser sessions for GTO Wizard.

## Features

- Create browser sessions that automatically navigate to GTO Wizard
- Generate unique session IDs for each browser instance
- Monitor session status and manage active sessions
- Close sessions when no longer needed
- **NEW**: Get-range action with solutions selection (Cash, MTT, Spin & Go, Hu SnG)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install
```

### 3. Run the Application

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Create Browser Session

**POST** `/create`

Creates a new browser session and opens the GTO Wizard URL.

**Request Body:**
```json
{
  "action": "create"
}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "launching",
  "message": "Browser session created successfully. Browser is launching in background."
}
```

### Get Range Action

**POST** `/get-range`

Performs range selector click and optionally clicks on a solutions button.

**Request Body:**
```json
{
  "action": "get-range",
  "session_id": "your-session-id",
  "solutions": "Cash"  // Optional: "Cash", "MTT", "Spin & Go", or "Hu SnG"
}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "success",
  "message": "Successfully clicked on range selector div and Cash solutions button",
  "action_performed": "clicked_range_selector_and_cash"
}
```

### List All Sessions

**GET** `/sessions`

Returns a list of all active browser sessions.

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "uuid-string",
      "status": "active",
      "url": "gto-wizard-url",
      "created_at": 1234567890.123
    }
  ],
  "total": 1
}
```

### Get Session Status

**GET** `/sessions/{session_id}`

Returns the status of a specific browser session.

### Close Session

**DELETE** `/sessions/{session_id}`

Closes a browser session and cleans up resources.

## Usage Examples

### Using curl

```bash
# Create a new browser session
curl -X POST "http://localhost:8000/create" \
  -H "Content-Type: application/json" \
  -d '{"action": "create"}'

# Get range with Cash solutions
curl -X POST "http://localhost:8000/get-range" \
  -H "Content-Type: application/json" \
  -d '{"action": "get-range", "session_id": "your-session-id", "solutions": "Cash"}'

# List all sessions
curl "http://localhost:8000/sessions"

# Close a specific session
curl -X DELETE "http://localhost:8000/sessions/{session_id}"
```

### Using Python requests

```python
import requests

# Create session
response = requests.post("http://localhost:8000/create", 
                        json={"action": "create"})
session_id = response.json()["session_id"]

# Get range with MTT solutions
response = requests.post("http://localhost:8000/get-range",
                        json={"action": "get-range", 
                              "session_id": session_id, 
                              "solutions": "MTT"})

# Check status
status = requests.get(f"http://localhost:8000/sessions/{session_id}")

# Close session
requests.delete(f"http://localhost:8000/sessions/{session_id}")
```

## Configuration

The application is configured to:
- Launch browsers in non-headless mode (visible)
- Use Chromium browser
- Set viewport to 1920x1080
- Use a realistic user agent string
- Wait for network idle when navigating to URLs

## Session Management

- Each session gets a unique UUID
- Sessions are stored in memory (will be lost on restart)
- Browser instances are kept open until explicitly closed
- Session status is tracked (launching, active, error)
- **NEW**: Sessions can perform multiple actions without restarting

## Solutions Selection

The get-range action supports four poker solutions:
- **Cash**: Clicks on Cash solutions button
- **MTT**: Clicks on MTT solutions button  
- **Spin & Go**: Clicks on Spin & Go solutions button
- **Hu SnG**: Clicks on Hu SnG solutions button

## Error Handling

- Invalid actions return 400 Bad Request
- Session not found returns 404 Not Found
- Internal errors return 500 Internal Server Error
- All errors are logged for debugging

## Notes

- The browser will remain open until the session is closed via API
- Multiple sessions can run simultaneously
- Each session opens the GTO Wizard URL in a separate browser window
- The application runs on port 8000 by default
- **NEW**: Server maintains browser sessions for multiple API calls
