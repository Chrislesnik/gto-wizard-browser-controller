from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
import asyncio
from playwright.async_api import async_playwright
import logging
from typing import Dict, Optional
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GTO Wizard Browser Controller", version="1.0.0")

# Store active browser sessions
active_sessions: Dict[str, dict] = {}

class CreateRequest(BaseModel):
    action: str = "create"

class CreateResponse(BaseModel):
    session_id: str
    status: str
    message: str

class GetRangeRequest(BaseModel):
    action: str = "get-range"
    session_id: str
    solutions: str | None = None  # Can be: "Cash", "MTT", "Spin & Go", "Hu SnG" or None

class GetRangeResponse(BaseModel):
    session_id: str
    status: str
    message: str
    action_performed: str

@app.get("/")
async def root():
    return {"message": "GTO Wizard Browser Controller API"}

@app.post("/create", response_model=CreateResponse)
async def create_browser_session(request: CreateRequest):
    """
    Create a new browser session and open the GTO Wizard URL
    """
    if request.action != "create":
        raise HTTPException(status_code=400, detail="Action must be 'create'")
    
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # GTO Wizard URL
        gto_wizard_url = "https://app.gtowizard.com/practice/range-builder?custree_id=929b2d3e-9830-448c-a6a4-e9218cba6504&cussol_id=cf42a022-e53a-438f-9997-02e36495104d&solution_type=gwiz&gmfs_solution_tab=ai_sols&gametype=MTTGeneral&depth=12.125&gmff_depth=100&gmfft_sort_key=0&gmfft_sort_order=desc&board=Js8d2d&history_spot=0"
        
        # Launch browser in background
        asyncio.create_task(launch_browser_session(session_id, gto_wizard_url))
        
        # Store session info
        active_sessions[session_id] = {
            "status": "launching",
            "url": gto_wizard_url,
            "created_at": asyncio.get_event_loop().time()
        }
        
        logger.info(f"Created new browser session: {session_id}")
        
        return CreateResponse(
            session_id=session_id,
            status="launching",
            message="Browser session created successfully. Browser is launching in background."
        )
        
    except Exception as e:
        logger.error(f"Error creating browser session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create browser session: {str(e)}")

@app.post("/get-range", response_model=GetRangeResponse)
async def get_range_action(request: GetRangeRequest):
    """
    Perform get-range action on an existing browser session
    """
    if request.action != "get-range":
        raise HTTPException(status_code=400, detail="Action must be 'get-range'")
    
    session_id = request.session_id
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_info = active_sessions[session_id]
    
    if session_info["status"] != "active":
        raise HTTPException(status_code=400, detail="Session is not active")
    
    try:
        page = session_info["page"]
        
        # Wait for the specific div to be present and clickable
        logger.info(f"Looking for GTO Wizard range selector div in session {session_id}")
        
        # Try multiple selectors to find the range selector div
        selectors = [
            "div.gmfover.text-noselect.gw_loading_text",
            "div.gmfover",
            "div[class*='gmfover']",
            "div[class*='gw_loading_text']"
        ]
        
        element_found = False
        for selector in selectors:
            try:
                # Wait for the element to be visible and clickable
                element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                if element:
                    # Click on the div
                    await element.click()
                    element_found = True
                    logger.info(f"Successfully clicked using selector: {selector}")
                    break
            except Exception as e:
                logger.warning(f"Selector {selector} failed: {str(e)}")
                continue
        
        if not element_found:
            raise Exception("Could not find or click on any range selector div")
        
        # Only perform the solutions click if the solutions parameter is provided
        if request.solutions:
            logger.info(f"Now clicking on solutions button for: {request.solutions}")
            
            # Map solutions to their corresponding data-tst attributes
            solutions_map = {
                "Cash": "chrow_cash",
                "MTT": "chrow_mtt", 
                "Spin & Go": "chrow_spins",
                "Hu SnG": "chrow_husn"
            }
            
            if request.solutions not in solutions_map:
                raise Exception(f"Invalid solutions value: {request.solutions}. Must be one of: Cash, MTT, Spin & Go, Hu SnG")
            
            data_tst_value = solutions_map[request.solutions]
            
            # Try multiple selectors for the solutions button
            solutions_selectors = [
                f"div[data-tst='{data_tst_value}']",
                f"div[data-tst='{data_tst_value}'] span",
                f"div:has-text('{request.solutions}')",
                f"text={request.solutions}"
            ]
            
            solutions_clicked = False
            for selector in solutions_selectors:
                try:
                    logger.info(f"Trying solutions selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on solutions button for {request.solutions}")
                        solutions_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Solutions selector {selector} failed: {str(e)}")
                    continue
            
            if not solutions_clicked:
                raise Exception(f"Could not click on solutions button for {request.solutions}")
            
            logger.info(f"Successfully clicked on range selector div and {request.solutions} solutions button in session {session_id}")
            
            return GetRangeResponse(
                session_id=session_id,
                status="success",
                message=f"Successfully clicked on range selector div and {request.solutions} solutions button",
                action_performed=f"clicked_range_selector_and_{request.solutions.lower().replace(' ', '_').replace('&', 'and')}"
            )
        else:
            # No solutions parameter provided, just return success for the first click
            logger.info(f"Successfully clicked on range selector div in session {session_id}")
            
            return GetRangeResponse(
                session_id=session_id,
                status="success",
                message="Successfully clicked on range selector div",
                action_performed="clicked_range_selector"
            )
        
    except Exception as e:
        logger.error(f"Error performing get-range action in session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to perform get-range action: {str(e)}")

async def launch_browser_session(session_id: str, url: str):
    """
    Launch a browser session with Playwright
    """
    try:
        playwright = await async_playwright().start()
        
        # Launch browser (you can customize these options)
        browser = await playwright.chromium.launch(
            headless=False,  # Set to True for headless mode
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--start-maximized',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        # Create new context and page
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Navigate to the URL
        logger.info(f"Navigating to GTO Wizard URL for session {session_id}")
        await page.goto(url, wait_until='networkidle')
        
        # Update session status
        active_sessions[session_id].update({
            "status": "active",
            "browser": browser,
            "context": context,
            "page": page,
            "playwright": playwright
        })
        
        logger.info(f"Browser session {session_id} is now active")
        
        # Keep the browser open (you can add logic here to handle session termination)
        # For now, we'll keep it running indefinitely
        
    except Exception as e:
        logger.error(f"Error in browser session {session_id}: {str(e)}")
        active_sessions[session_id]["status"] = "error"
        active_sessions[session_id]["error"] = str(e)

@app.get("/sessions")
async def list_sessions():
    """
    List all active browser sessions
    """
    session_list = []
    for session_id, session_info in active_sessions.items():
        session_list.append({
            "session_id": session_id,
            "status": session_info["status"],
            "url": session_info["url"],
            "created_at": session_info["created_at"]
        })
    
    return {"sessions": session_list, "total": len(session_list)}

@app.get("/sessions/{session_id}")
async def get_session_status(session_id: str):
    """
    Get status of a specific browser session
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_info = active_sessions[session_id]
    return {
        "session_id": session_id,
        "status": session_info["status"],
        "url": session_info["url"],
        "created_at": session_info["created_at"]
    }

@app.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    """
    Close a browser session
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        session_info = active_sessions[session_id]
        
        if session_info["status"] == "active":
            # Close browser resources
            if "page" in session_info:
                await session_info["page"].close()
            if "context" in session_info:
                await session_info["context"].close()
            if "browser" in session_info:
                await session_info["browser"].close()
            if "playwright" in session_info:
                await session_info["playwright"].stop()
        
        # Remove from active sessions
        del active_sessions[session_id]
        
        logger.info(f"Closed browser session: {session_id}")
        return {"message": f"Session {session_id} closed successfully"}
        
    except Exception as e:
        logger.error(f"Error closing session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to close session: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
