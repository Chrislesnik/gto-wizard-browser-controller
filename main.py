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
    solutions: Optional[str] = None  # Can be: "Cash", "MTT", "Spin & Go", "Hu SnG" or None
    cash_type: Optional[str] = None  # Can be: "Classic", "Short", "Ante", "Straddle", "Straddle+Ante", "DoubleStraddle", "MississippiStraddle" or None
    cash_players: Optional[str] = None  # Can be: "Heads-up", "6max", "8max", "9max" or None
    available_spots: Optional[str] = None  # Can be: "postflop_included", "preflop_only" or None
    cash_stacks: Optional[str] = None  # Can be: "Any", "200", "150", "100", "75", "50", "40", "20" or None

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
        
        # Only perform the solutions click if the solutions parameter is provided and not empty
        if request.solutions and request.solutions.strip():
            logger.info(f"Now clicking on solutions button for: {request.solutions}")
            
            # Map solutions to their corresponding data-tst attributes
            solutions_map = {
                "Cash": "chrow_cash",
                "MTT": "chrow_mtt", 
                "Spin & Go": "chrow_spins",
                "Hu SnG": "chrow_husng"
            }
            
            if request.solutions not in solutions_map:
                raise Exception(f"Invalid solutions value: {request.solutions}. Must be one of: Cash, MTT, Spin & Go, Hu SnG")
            
            data_tst_value = solutions_map[request.solutions]
            
            # Try multiple selectors for the solutions button
            solutions_selectors = [
                f"div[data-tst='{data_tst_value}']",
                f"div[data-tst='{data_tst_value}'] span",
                f"div:has-text('{request.solutions}')",
                f"text={request.solutions}",
                f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.solutions}')"
            ]
            
            solutions_clicked = False
            for selector in solutions_selectors:
                try:
                    logger.info(f"Trying solutions selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on solutions button for {request.solutions}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.solutions} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.solutions} button is active, but click was successful")
                        
                        solutions_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Solutions selector {selector} failed: {str(e)}")
                    continue
            
            if not solutions_clicked:
                raise Exception(f"Could not click on solutions button for {request.solutions}")
            
            logger.info(f"Successfully clicked on range selector div and {request.solutions} solutions button in session {session_id}")
            
            # Continue to cash_type logic if solutions was successful
            pass
        else:
            # No solutions parameter provided or empty, just continue to cash_type logic
            logger.info(f"No solutions parameter provided or empty - skipping solutions selection. Successfully clicked on range selector div in session {session_id}")
        
        # Handle cash_type clicking if provided
        if request.cash_type and request.cash_type.strip():
            logger.info(f"Now clicking on cash_type button for: {request.cash_type}")
            
            # Map cash_type to their corresponding data-tst attributes
            cash_type_map = {
                "Classic": "chrow_classic",
                "Short": "chrow_shortstack", 
                "Ante": "chrow_ante",
                "Straddle": "chrow_straddle",
                "Straddle+Ante": "chrow_ante_straddle",
                "DoubleStraddle": "chrow_double_straddle",
                "MississippiStraddle": "chrow_mississippi_straddle"
            }
            
            if request.cash_type not in cash_type_map:
                raise Exception(f"Invalid cash_type value: {request.cash_type}. Must be one of: Classic, Short, Ante, Straddle, Straddle+Ante, DoubleStraddle, MississippiStraddle")
            
            data_tst_value = cash_type_map[request.cash_type]
            
            # Try multiple selectors for the cash_type button
            cash_type_selectors = [
                f"div[data-tst='{data_tst_value}']",
                f"div[data-tst='{data_tst_value}'] span",
                f"div:has-text('{request.cash_type}')",
                f"text={request.cash_type}",
                f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.cash_type}')"
            ]
            
            cash_type_clicked = False
            for selector in cash_type_selectors:
                try:
                    logger.info(f"Trying cash_type selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on cash_type button for {request.cash_type}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.cash_type} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.cash_type} button is active, but click was successful")
                        
                        cash_type_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Cash_type selector {selector} failed: {str(e)}")
                    continue
            
            if not cash_type_clicked:
                raise Exception(f"Could not click on cash_type button for {request.cash_type}")
        
        # Handle cash_players clicking if provided
        if request.cash_players and request.cash_players.strip():
            logger.info(f"Now clicking on cash_players button for: {request.cash_players}")
            
            # Map cash_players to their corresponding data-tst attributes
            cash_players_map = {
                "Heads-up": "chrow_hu",
                "6max": "chrow_6max", 
                "8max": "chrow_8max",
                "9max": "chrow_9max"
            }
            
            if request.cash_players not in cash_players_map:
                raise Exception(f"Invalid cash_players value: {request.cash_players}. Must be one of: Heads-up, 6max, 8max, 9max")
            
            data_tst_value = cash_players_map[request.cash_players]
            
            # Try multiple selectors for the cash_players button
            cash_players_selectors = [
                f"div[data-tst='{data_tst_value}']",
                f"div[data-tst='{data_tst_value}'] span",
                f"div:has-text('{request.cash_players}')",
                f"text={request.cash_players}",
                f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.cash_players}')"
            ]
            
            cash_players_clicked = False
            for selector in cash_players_selectors:
                try:
                    logger.info(f"Trying cash_players selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on cash_players button for {request.cash_players}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.cash_players} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.cash_players} button is active, but click was successful")
                        
                        cash_players_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Cash_players selector {selector} failed: {str(e)}")
                    continue
            
            if not cash_players_clicked:
                raise Exception(f"Could not click on cash_players button for {request.cash_players}")
        
        # Handle available_spots clicking if provided
        if request.available_spots and request.available_spots.strip():
            logger.info(f"Now clicking on available_spots button for: {request.available_spots}")
            
            # Map available_spots to their corresponding data-tst attributes and display text
            available_spots_map = {
                "postflop_included": {"data_tst": "chrow_all_spots", "display_text": "Postflop included"},
                "preflop_only": {"data_tst": "chrow_preflop_only", "display_text": "Preflop only"}
            }
            
            if request.available_spots not in available_spots_map:
                raise Exception(f"Invalid available_spots value: {request.available_spots}. Must be one of: postflop_included, preflop_only")
            
            data_tst_value = available_spots_map[request.available_spots]["data_tst"]
            display_text = available_spots_map[request.available_spots]["display_text"]
            
            # Try multiple selectors for the available_spots button
            available_spots_selectors = [
                f"div[data-tst='{data_tst_value}']",
                f"div[data-tst='{data_tst_value}'] span",
                f"div:has-text('{display_text}')",
                f"text={display_text}",
                f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{display_text}')"
            ]
            
            available_spots_clicked = False
            for selector in available_spots_selectors:
                try:
                    logger.info(f"Trying available_spots selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on available_spots button for {request.available_spots}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.available_spots} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.available_spots} button is active, but click was successful")
                        
                        available_spots_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Available_spots selector {selector} failed: {str(e)}")
                    continue
            
            if not available_spots_clicked:
                raise Exception(f"Could not click on available_spots button for {request.available_spots}")
        
        # Handle cash_stacks clicking if provided
        if request.cash_stacks and request.cash_stacks.strip():
            logger.info(f"Now clicking on cash_stacks button for: {request.cash_stacks}")
            
            # Map cash_stacks to their corresponding data-tst attributes
            cash_stacks_map = {
                "Any": "chrow_any",
                "200": "chrow_200",
                "150": "chrow_150", 
                "100": "chrow_100",
                "75": "chrow_75",
                "50": "chrow_50",
                "40": "chrow_40",
                "20": "chrow_20"
            }
            
            if request.cash_stacks not in cash_stacks_map:
                raise Exception(f"Invalid cash_stacks value: {request.cash_stacks}. Must be one of: Any, 200, 150, 100, 75, 50, 40, 20")
            
            data_tst_value = cash_stacks_map[request.cash_stacks]
            
            # Try multiple selectors for the cash_stacks button
            cash_stacks_selectors = [
                f"div[data-tst='{data_tst_value}']",
                f"div[data-tst='{data_tst_value}'] span",
                f"div:has-text('{request.cash_stacks}')",
                f"text={request.cash_stacks}",
                f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.cash_stacks}')"
            ]
            
            cash_stacks_clicked = False
            for selector in cash_stacks_selectors:
                try:
                    logger.info(f"Trying cash_stacks selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on cash_stacks button for {request.cash_stacks}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.cash_stacks} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.cash_stacks} button is active, but click was successful")
                        
                        cash_stacks_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Cash_stacks selector {selector} failed: {str(e)}")
                    continue
            
            if not cash_stacks_clicked:
                raise Exception(f"Could not click on cash_stacks button for {request.cash_stacks}")
        
        # Build response message and action based on what was performed
        actions_performed = []
        message_parts = ["Successfully clicked on range selector div"]
        
        if request.solutions and request.solutions.strip():
            actions_performed.append(f"clicked_{request.solutions.lower().replace(' ', '_').replace('&', 'and')}")
            message_parts.append(f"{request.solutions} solutions button")
        
        if request.cash_type and request.cash_type.strip():
            actions_performed.append(f"clicked_{request.cash_type.lower().replace(' ', '_').replace('+', 'plus').replace('&', 'and')}")
            message_parts.append(f"{request.cash_type} cash_type button")
        
        if request.cash_players and request.cash_players.strip():
            actions_performed.append(f"clicked_{request.cash_players.lower().replace(' ', '_').replace('-', '_')}")
            message_parts.append(f"{request.cash_players} cash_players button")
        
        if request.available_spots and request.available_spots.strip():
            actions_performed.append(f"clicked_{request.available_spots.lower().replace(' ', '_').replace('-', '_')}")
            message_parts.append(f"{request.available_spots} available_spots button")
        
        if request.cash_stacks and request.cash_stacks.strip():
            actions_performed.append(f"clicked_{request.cash_stacks.lower()}")
            message_parts.append(f"{request.cash_stacks} cash_stacks button")
        
        action_performed = "_and_".join(actions_performed) if actions_performed else "clicked_range_selector"
        message = " and ".join(message_parts)
        
        logger.info(f"Successfully completed all actions in session {session_id}: {message}")
        
        return GetRangeResponse(
            session_id=session_id,
            status="success",
            message=message,
            action_performed=action_performed
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
        browser = await playwright.firefox.launch(
            headless=False  # Set to True for headless mode
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
