import cloudscraper
import getpass
import json
import os
import pickle
import requests
import sys
import time
import webbrowser

from requests_futures.sessions import FuturesSession
from concurrent.futures import as_completed
from fuzzywuzzy import fuzz
import steam.webauth as wa


# Steam urls
STEAM_KEYS_PAGE = "https://store.steampowered.com/account/registerkey"
STEAM_REDEEM_API = "https://store.steampowered.com/account/ajaxregisterkey/"

# http headers for requests
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

# Get cookies to attempt to skip manual login
def try_recover_cookies(cookie_file, session):
    try:
        with open(cookie_file, "rb") as file:
            session.cookies.update(pickle.load(file))
        return True
    except:
        return False

# Export cookies 
def export_cookies(cookie_file, session):
    try:
        with open(cookie_file, "wb") as file:
            pickle.dump(session.cookies, file)
        return True
    except:
        return False


# Make sure we successfully logged in
def verify_logins_session(session):
    r = session.get(STEAM_KEYS_PAGE, allow_redirects=False)
    loggedin = (r.status_code != 301 and r.status_code != 302)
    return loggedin


def steam_login():
    # Login to steam. Try to use saved login from cookies if possible
    r = requests.Session()
    if try_recover_cookies(".steamcookies", r) and verify_logins_session(r)[1]:
        return r

    # If login cookie cant be found, login manually with username,pw,2FA
    s_username = input("Steam Username: ")
    user = wa.WebAuth(s_username)
    session = user.cli_login()
    export_cookies(".steamcookies", session)
    return session


def redeem_key(session, key, quiet=False):
    # Return if empty key (shouldnt happen since we skip newlines, 
    # but joe and matt are dicks who wouldnt know this)
    if key == "":
        return 0
    # Set the session ID from the cookie so we can make the request
    session_id = session.cookies.get_dict()["sessionid"]
    # Make the request
    response = session.post(STEAM_REDEEM_API, data={"product_key": key, "sessionid": session_id})
    # Get the json blob from the request body
    blob = response.json()

    # Check that the key was successfully redeemed and return if so
    if blob["success"] == 1:
        for item in blob["purchase_receipt_info"]["line_items"]:
            print("Redeemed " + item["line_item_description"])
        return 0
    # If key failed to be redeemed, get error code and inform user
    else:
        error_code = blob.get("purchase_result_details")
        if error_code == None:
            # Sometimes details are blank, so pull error code from receipt info
            error_code = blob.get("purchase_receipt_info")
            if error_code != None:
                error_code = error_code.get("result_detail")
        error_code = error_code or 53

        if error_code == 9:
            error_message = (
                "This Steam account already owns the product(s) contained in this offer. To access them, "
                "visit your library in the Steam client. "
            )
        elif error_code == 13:
            error_message = (
                "Sorry, but this product is not available for purchase in this country. Your product key "
                "has not been redeemed. "
            )
        elif error_code == 14:
            error_message = (
                "The product code you've entered is not valid. Please double check to see if you've "
                "mistyped your key. I, L, and 1 can look alike, as can V and Y, and 0 and O. "
            )
        elif error_code == 15:
            error_message = (
                "The product code you've entered has already been activated by a different Steam account. "
                "This code cannot be used again. Please contact the retailer or online seller where the "
                "code was purchased for assistance. "
            )
        elif error_code == 24:
            error_message = (
                "The product code you've entered requires ownership of another product before "
                "activation.\n\nIf you are trying to activate an expansion pack or downloadable content, "
                "please first activate the original game, then activate this additional content. "
            )
        elif error_code == 36:
            error_message = (
                "The product code you have entered requires that you first play this game on the "
                "PlayStation®3 system before it can be registered.\n\nPlease:\n\n- Start this game on "
                "your PlayStation®3 system\n\n- Link your Steam account to your PlayStation®3 Network "
                "account\n\n- Connect to Steam while playing this game on the PlayStation®3 system\n\n- "
                "Register this product code through Steam. "
            )
        elif error_code == 53:
            error_message = (
                "There have been too many recent activation attempts from this account or Internet "
                "address. Please wait and try your product code again later. "
            )
        else:
            error_message = (
                "An unexpected error has occurred.  Your product code has not been redeemed.  Please wait "
                "30 minutes and try redeeming the code again.  If the problem persists, please contact <a "
                'href="https://help.steampowered.com/en/wizard/HelpWithCDKey">Steam Support</a> for '
                "further assistance. "
            )
        if error_code != 53 or not quiet:
            print(error_message)
        return error_code


def redeem_steam_keys(steam_keys):
    session = steam_login()

    print("Successfully signed in on Steam.")

    for key in steam_keys:
        code = redeem_key(session, key)
        animation = "|/-\\"
        seconds = 0
        while code == 53:
            """NOTE
            Steam seems to limit to about 50 keys/hr -- even if all 50 keys are legitimate *sigh*
            Even worse: 10 *failed* keys/hr
            Duplication counts towards Steam's _failure rate limit_,
            hence why we've worked so hard above to figure out what we already own
            """
            current_animation = animation[seconds % len(animation)]
            print(
                f"Waiting for rate limit to go away (takes an hour after first key insert) {current_animation}",
                end="\r",
            )
            time.sleep(1)
            seconds = seconds + 1
            if seconds % 60 == 0:
                # Try again every 60 seconds
                code = _redeem_steam(session, key["redeemed_key_val"], quiet=True)


with open("keys.txt") as k:
    steam_keys=[line.strip() for line in k]

redeem_steam_keys(steam_keys)