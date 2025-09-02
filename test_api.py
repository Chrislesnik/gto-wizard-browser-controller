#!/usr/bin/env python3
"""
Test script for the GTO Wizard Browser Controller API
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_create_session() -> Dict[str, Any]:
    """Test creating a new browser session"""
    print("Testing session creation...")
    
    response = requests.post(
        f"{BASE_URL}/create",
        json={"action": "create"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Session created successfully!")
        print(f"   Session ID: {data['session_id']}")
        print(f"   Status: {data['status']}")
        print(f"   Message: {data['message']}")
        return data
    else:
        print(f"❌ Failed to create session: {response.status_code}")
        print(f"   Response: {response.text}")
        return {}

def test_list_sessions():
    """Test listing all sessions"""
    print("\nTesting session listing...")
    
    response = requests.get(f"{BASE_URL}/sessions")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Sessions listed successfully!")
        print(f"   Total sessions: {data['total']}")
        
        for session in data['sessions']:
            print(f"   - {session['session_id']}: {session['status']}")
    else:
        print(f"❌ Failed to list sessions: {response.status_code}")
        print(f"   Response: {response.text}")

def test_get_session_status(session_id: str):
    """Test getting session status"""
    print(f"\nTesting session status for {session_id}...")
    
    response = requests.get(f"{BASE_URL}/sessions/{session_id}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Session status retrieved successfully!")
        print(f"   Status: {data['status']}")
        print(f"   URL: {data['url']}")
    else:
        print(f"❌ Failed to get session status: {response.status_code}")
        print(f"   Response: {response.text}")

def test_close_session(session_id: str):
    """Test closing a session"""
    print(f"\nTesting session closure for {session_id}...")
    
    response = requests.delete(f"{BASE_URL}/sessions/{session_id}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Session closed successfully!")
        print(f"   Message: {data['message']}")
    else:
        print(f"❌ Failed to close session: {response.status_code}")
        print(f"   Response: {response.text}")

def test_invalid_action():
    """Test invalid action parameter"""
    print("\nTesting invalid action...")
    
    response = requests.post(
        f"{BASE_URL}/create",
        json={"action": "invalid"}
    )
    
    if response.status_code == 400:
        print("✅ Invalid action correctly rejected!")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Expected 400 error, got {response.status_code}")

def main():
    """Main test function"""
    print("🚀 Starting GTO Wizard Browser Controller API Tests")
    print("=" * 50)
    
    # Test root endpoint
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ API is running and accessible")
        else:
            print("❌ API is not responding correctly")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure it's running on localhost:8000")
        return
    
    # Test invalid action first
    test_invalid_action()
    
    # Test session creation
    session_data = test_create_session()
    if not session_data:
        print("❌ Cannot continue tests without a valid session")
        return
    
    session_id = session_data['session_id']
    
    # Wait a bit for browser to launch
    print("\n⏳ Waiting for browser to launch...")
    time.sleep(3)
    
    # Test getting session status
    test_get_session_status(session_id)
    
    # Test listing sessions
    test_list_sessions()
    
    # Wait a bit more to see the browser
    print("\n⏳ Keeping browser open for 10 seconds so you can see it...")
    time.sleep(10)
    
    # Test closing session
    test_close_session(session_id)
    
    # Verify session is closed
    print("\n⏳ Verifying session closure...")
    time.sleep(2)
    test_list_sessions()
    
    print("\n🎉 All tests completed!")

if __name__ == "__main__":
    main()
