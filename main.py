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
    bet_sizes: Optional[str] = None  # Can be: "Any", "Simple", "Simplified", "General" or None
    rake: Optional[str] = None  # Can be: "Any", "NL50", "NL500", "NL50 GG", "NL1k GG" or None
    cash_open_size: Optional[str] = None  # Can be: "Any", "GTO", "2.5x" or None
    cash_3bet_size: Optional[str] = None  # Can be: "Any", "GTO", "Smaller" or None
    hero: Optional[str] = None  # Can be: "Any", "OOP", "IP" or None

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
        
        # Wait for the page to be fully loaded
        logger.info(f"Waiting for GTO Wizard page to load in session {session_id}")
        
        # Wait for the page to be ready - look for any GTO Wizard specific elements
        try:
            # Wait for any GTO Wizard button to be present (this indicates the page is loaded)
            await page.wait_for_selector("div.gw_btn", state="visible", timeout=10000)
            logger.info("GTO Wizard page loaded successfully")
        except Exception as e:
            logger.warning(f"Could not find GTO Wizard buttons, but continuing: {str(e)}")
        
        # Try to find and click the range selector div, but don't fail if we can't find it
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
                element = await page.wait_for_selector(selector, state="visible", timeout=3000)
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
            logger.warning("Could not find or click on any range selector div, but continuing with other actions")
        
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
        
        # Handle bet_sizes clicking if provided
        if request.bet_sizes and request.bet_sizes.strip():
            logger.info(f"Now clicking on bet_sizes button for: {request.bet_sizes}")
            
            # Map bet_sizes to their corresponding data-tst attributes
            bet_sizes_map = {
                "Any": "chrow_any",
                "Simple": "chrow_simple",
                "Simplified": "chrow_simplified", 
                "General": "chrow_general"
            }
            
            if request.bet_sizes not in bet_sizes_map:
                raise Exception(f"Invalid bet_sizes value: {request.bet_sizes}. Must be one of: Any, Simple, Simplified, General")
            
            data_tst_value = bet_sizes_map[request.bet_sizes]
            
            # Try multiple selectors for the bet_sizes button
            bet_sizes_selectors = [
                f"div[data-tst='{data_tst_value}']",
                f"div[data-tst='{data_tst_value}'] span",
                f"div:has-text('{request.bet_sizes}')",
                f"text={request.bet_sizes}",
                f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.bet_sizes}')"
            ]
            
            bet_sizes_clicked = False
            for selector in bet_sizes_selectors:
                try:
                    logger.info(f"Trying bet_sizes selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on bet_sizes button for {request.bet_sizes}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.bet_sizes} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.bet_sizes} button is active, but click was successful")
                        
                        bet_sizes_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Bet_sizes selector {selector} failed: {str(e)}")
                    continue
            
            if not bet_sizes_clicked:
                raise Exception(f"Could not click on bet_sizes button for {request.bet_sizes}")
        
        # Handle rake clicking if provided
        if request.rake and request.rake.strip():
            logger.info(f"Now clicking on rake button for: {request.rake}")
            
            # Map rake to their corresponding data-tst attributes
            rake_map = {
                "Any": "chrow_any",
                "NL50": "chrow_NL50",
                "NL500": "chrow_NL500", 
                "NL50 GG": "chrow_GG NL50",
                "NL1k GG": "chrow_GG NL1k"
            }
            
            if request.rake not in rake_map:
                raise Exception(f"Invalid rake value: {request.rake}. Must be one of: Any, NL50, NL500, NL50 GG, NL1k GG")
            
            data_tst_value = rake_map[request.rake]
            
            # Try multiple selectors for the rake button
            rake_selectors = [
                f"div[data-tst='{data_tst_value}']",
                f"div[data-tst='{data_tst_value}'] span",
                f"div:has-text('{request.rake}')",
                f"text={request.rake}",
                f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.rake}')"
            ]
            
            rake_clicked = False
            for selector in rake_selectors:
                try:
                    logger.info(f"Trying rake selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on rake button for {request.rake}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.rake} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.rake} button is active, but click was successful")
                        
                        rake_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Rake selector {selector} failed: {str(e)}")
                    continue
            
            if not rake_clicked:
                raise Exception(f"Could not click on rake button for {request.rake}")
        
        # Handle cash_open_size clicking if provided
        if request.cash_open_size and request.cash_open_size.strip():
            logger.info(f"Now clicking on cash_open_size button for: {request.cash_open_size}")
            
            # Map cash_open_size to their corresponding data-tst attributes
            # Note: "Any" might conflict with other sections, so we'll rely more on text selectors
            cash_open_size_map = {
                "Any": "chrow_any",  # This might conflict, but we have fallback selectors
                "GTO": "chrow_gto",
                "2.5x": "chrow_25x"
            }
            
            if request.cash_open_size not in cash_open_size_map:
                raise Exception(f"Invalid cash_open_size value: {request.cash_open_size}. Must be one of: Any, GTO, 2.5x")
            
            data_tst_value = cash_open_size_map[request.cash_open_size]
            
            # Try multiple selectors for the cash_open_size button
            # For "Any", we need to be more specific since it appears in multiple sections
            if request.cash_open_size == "Any":
                cash_open_size_selectors = [
                    # Try to find "Any" button specifically in the opening size section
                    f"div:has-text('Opening'):has-text('Any')",
                    f"div:has-text('{request.cash_open_size}'):near(div:has-text('Opening'))",
                    f"div[data-tst='{data_tst_value}']",
                    f"div[data-tst='{data_tst_value}'] span",
                    f"div:has-text('{request.cash_open_size}')",
                    f"text={request.cash_open_size}",
                    f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.cash_open_size}')"
                ]
            else:
                cash_open_size_selectors = [
                    f"div[data-tst='{data_tst_value}']",
                    f"div[data-tst='{data_tst_value}'] span",
                    f"div:has-text('{request.cash_open_size}')",
                    f"text={request.cash_open_size}",
                    f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.cash_open_size}')"
                ]
            
            cash_open_size_clicked = False
            for selector in cash_open_size_selectors:
                try:
                    logger.info(f"Trying cash_open_size selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on cash_open_size button for {request.cash_open_size}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.cash_open_size} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.cash_open_size} button is active, but click was successful")
                        
                        cash_open_size_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Cash_open_size selector {selector} failed: {str(e)}")
                    continue
            
            if not cash_open_size_clicked:
                raise Exception(f"Could not click on cash_open_size button for {request.cash_open_size}")
        
        # Handle cash_3bet_size clicking if provided
        if request.cash_3bet_size and request.cash_3bet_size.strip():
            logger.info(f"Now clicking on cash_3bet_size button for: {request.cash_3bet_size}")
            
            # Map cash_3bet_size to their corresponding data-tst attributes
            # Note: These might conflict with other sections, so we'll use more specific selectors
            cash_3bet_size_map = {
                "Any": "chrow_any",
                "GTO": "chrow_gto", 
                "Smaller": "chrow_smaller"
            }
            
            if request.cash_3bet_size not in cash_3bet_size_map:
                raise Exception(f"Invalid cash_3bet_size value: {request.cash_3bet_size}. Must be one of: Any, GTO, Smaller")
            
            data_tst_value = cash_3bet_size_map[request.cash_3bet_size]
            
            # Try multiple selectors for the cash_3bet_size button
            # We need to be very specific to target the 3bet size section, not other sections
            # Use "Smaller" as a reference point since it's unique to the 3bet section
            if request.cash_3bet_size == "Any":
                cash_3bet_size_selectors = [
                    # The "Any" button in 3bet section has NO data-tst attribute
                    # We need to find the "Any" button that is specifically in the 3bet section
                    # Look for the "Any" button that comes before the "GTO" button that comes before the "Smaller" button
                    f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('Any'):near(div[data-tst='chrow_smaller']):not(:has([data-tst]))",
                    # Try to find "Any" button that is the first button in a row that contains "Smaller"
                    f"div:has-text('Any'):near(div:has-text('Smaller')):not([data-tst])",
                    # Look for "Any" button that is near both "GTO" and "Smaller" buttons
                    f"div:has-text('Any'):near(div:has-text('GTO')):near(div:has-text('Smaller'))",
                    # Fallback selectors
                    f"div:has-text('Any'):near(div[data-tst='chrow_smaller'])",
                    f"div:has-text('{request.cash_3bet_size}')",
                    f"text={request.cash_3bet_size}",
                    f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.cash_3bet_size}')"
                ]
            elif request.cash_3bet_size == "GTO":
                cash_3bet_size_selectors = [
                    # The "GTO" button in 3bet section has data-tst="chrow_gto" but conflicts with opening size section
                    # We need to find the "GTO" button that is specifically in the 3bet section
                    # Use a very specific selector that targets the GTO button in the 3bet section by looking for the unique combination
                    # Find GTO button that is near Smaller (unique to 3bet section) but NOT near 2.5x (unique to opening section)
                    f"div[data-tst='chrow_gto']:near(div[data-tst='chrow_smaller']):not(:near(div:has-text('2.5x')))",
                    # Try to find GTO button that is near Smaller but not near Opening
                    f"div[data-tst='chrow_gto']:near(div[data-tst='chrow_smaller']):not(:near(div:has-text('Opening')))",
                    # Look for GTO button that is near both Any (no data-tst) and Smaller buttons
                    f"div[data-tst='chrow_gto']:near(div:has-text('Any'):not([data-tst])):near(div[data-tst='chrow_smaller'])",
                    # Use CSS sibling selectors to find the GTO button that comes after Any (no data-tst) and before Smaller
                    f"div:has-text('Any'):not([data-tst]) + div[data-tst='chrow_gto']",
                    f"div:has-text('Any'):not([data-tst]) ~ div[data-tst='chrow_gto']",
                    # Look for GTO button that has Smaller as a sibling
                    f"div[data-tst='chrow_gto']:has(+ div[data-tst='chrow_smaller'])",
                    f"div[data-tst='chrow_gto']:has(~ div[data-tst='chrow_smaller'])",
                    # Look for "GTO" button that is near both "Any" and "Smaller" buttons
                    f"div:has-text('GTO'):near(div:has-text('Any')):near(div:has-text('Smaller'))",
                    # Fallback selectors
                    f"div:has-text('{request.cash_3bet_size}'):near(div:has-text('Smaller'))",
                    f"div:has-text('{request.cash_3bet_size}'):near(div[data-tst='chrow_smaller'])",
                    f"div[data-tst='{data_tst_value}']",
                    f"div[data-tst='{data_tst_value}'] span",
                    f"div:has-text('{request.cash_3bet_size}')",
                    f"text={request.cash_3bet_size}",
                    f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.cash_3bet_size}')"
                ]
            else:  # Smaller
                cash_3bet_size_selectors = [
                    # Try the specific data-tst first (Smaller should be unique)
                    f"div[data-tst='{data_tst_value}']",
                    f"div[data-tst='{data_tst_value}'] span",
                    # Fallback to generic selectors
                    f"div:has-text('{request.cash_3bet_size}')",
                    f"text={request.cash_3bet_size}",
                    f"div.gw_btn.gw_btn_text.gw_loading_text.cherow_row_checkbox.cherow_row_checkbox_item:has-text('{request.cash_3bet_size}')"
                ]
            
            cash_3bet_size_clicked = False
            for selector in cash_3bet_size_selectors:
                try:
                    logger.info(f"Trying cash_3bet_size selector: {selector}")
                    element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                    if element:
                        await element.click()
                        logger.info(f"Successfully clicked on cash_3bet_size button for {request.cash_3bet_size}")
                        
                        # Wait a moment for the click to register
                        await page.wait_for_timeout(1000)
                        
                        # Verify that the button is now active
                        # Use more specific verification selectors to avoid conflicts
                        if request.cash_3bet_size == "Any":
                            # The "Any" button in 3bet section has NO data-tst attribute
                            active_selector = f"div:has-text('Any'):near(div:has-text('Smaller')):not([data-tst]).gw_btn_active"
                        elif request.cash_3bet_size == "GTO":
                            # The "GTO" button in 3bet section has data-tst="chrow_gto" but we need to verify it's the right one
                            # Verify it's the GTO button that's near the Smaller button and not near 2.5x
                            active_selector = f"div[data-tst='chrow_gto']:near(div[data-tst='chrow_smaller']):not(:near(div:has-text('2.5x'))).gw_btn_active"
                        else:  # Smaller
                            active_selector = f"div[data-tst='{data_tst_value}'].gw_btn_active"
                        
                        try:
                            await page.wait_for_selector(active_selector, state="visible", timeout=3000)
                            logger.info(f"Verified that {request.cash_3bet_size} button is now active")
                        except:
                            logger.warning(f"Could not verify that {request.cash_3bet_size} button is active, but click was successful")
                        
                        cash_3bet_size_clicked = True
                        break
                except Exception as e:
                    logger.info(f"Cash_3bet_size selector {selector} failed: {str(e)}")
                    continue
            
            if not cash_3bet_size_clicked:
                raise Exception(f"Could not click on cash_3bet_size button for {request.cash_3bet_size}")
        
        # Handle hero clicking if provided
        if request.hero and request.hero.strip():
            logger.info(f"Now clicking on hero button for: {request.hero}")
            
            # Map hero to their corresponding data-tst attributes
            hero_map = {
                "Any": None,  # "Any" has no data-tst attribute
                "OOP": "chrow_oop",
                "IP": "chrow_ip"
            }
            
            if request.hero not in hero_map:
                raise Exception(f"Invalid hero value: {request.hero}. Must be one of: Any, OOP, IP")
            
            data_tst_value = hero_map[request.hero]
            
            # Simple approach: Find the Hero section first, then find the specific button within it
            hero_clicked = False
            
            if request.hero == "OOP":
                logger.info("Looking for OOP button with exact HTML structure from image")
                
                # Try to find and click the OOP button
                oop_selectors = [
                    "div[data-tst='chrow_oop']",
                    "div:has-text('OOP')",
                    "div.gw_btn:has-text('OOP')"
                ]
                
                for selector in oop_selectors:
                    try:
                        logger.info(f"Trying OOP selector: {selector}")
                        element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                        if element:
                            await element.click()
                            logger.info(f"Successfully clicked on OOP button using selector: {selector}")
                            await page.wait_for_timeout(1000)
                            hero_clicked = True
                            break
                    except Exception as e:
                        logger.info(f"OOP selector {selector} failed: {str(e)}")
                        continue
            
            elif request.hero == "IP":
                logger.info("Looking for IP button")
                ip_selectors = [
                    "div[data-tst='chrow_ip']",
                    "div:has-text('IP')",
                    "div.gw_btn:has-text('IP')"
                ]
                
                for selector in ip_selectors:
                    try:
                        logger.info(f"Trying IP selector: {selector}")
                        element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                        if element:
                            await element.click()
                            logger.info(f"Successfully clicked on IP button using selector: {selector}")
                            await page.wait_for_timeout(1000)
                            hero_clicked = True
                            break
                    except Exception as e:
                        logger.info(f"IP selector {selector} failed: {str(e)}")
                        continue
            
            elif request.hero == "Any":
                logger.info("Looking for Any button")
                any_selectors = [
                    "div:has-text('Any'):not([data-tst])",
                    "div.gw_btn:has-text('Any')"
                ]
                
                for selector in any_selectors:
                    try:
                        logger.info(f"Trying Any selector: {selector}")
                        element = await page.wait_for_selector(selector, state="visible", timeout=5000)
                        if element:
                            await element.click()
                            logger.info(f"Successfully clicked on Any button using selector: {selector}")
                            await page.wait_for_timeout(1000)
                            hero_clicked = True
                            break
                    except Exception as e:
                        logger.info(f"Any selector {selector} failed: {str(e)}")
                        continue
                
                if not hero_clicked:
                    raise Exception(f"Could not click on hero button for {request.hero}")
        
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
        
        if request.bet_sizes and request.bet_sizes.strip():
            actions_performed.append(f"clicked_{request.bet_sizes.lower()}")
            message_parts.append(f"{request.bet_sizes} bet_sizes button")
        
        if request.rake and request.rake.strip():
            actions_performed.append(f"clicked_{request.rake.lower().replace(' ', '_').replace('k', 'k')}")
            message_parts.append(f"{request.rake} rake button")
        
        if request.cash_open_size and request.cash_open_size.strip():
            actions_performed.append(f"clicked_{request.cash_open_size.lower().replace('.', '_')}")
            message_parts.append(f"{request.cash_open_size} cash_open_size button")
        
        if request.cash_3bet_size and request.cash_3bet_size.strip():
            actions_performed.append(f"clicked_{request.cash_3bet_size.lower()}")
            message_parts.append(f"{request.cash_3bet_size} cash_3bet_size button")
        
        if request.hero and request.hero.strip():
            actions_performed.append(f"clicked_{request.hero.lower()}")
            message_parts.append(f"{request.hero} hero button")
        
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
