# -*- coding: utf-8 -*-
import configparser
import datetime
import json
import logging
import os
import platform
import psutil
import re
import requests
import shutil
import signal
import sys
import time
import webbrowser

# Attempt optional rich import for better console output
try:
    from rich.console import Console
    from rich.logging import RichHandler
    console = Console()
    USE_RICH = True
except ImportError:
    console = None # Fallback if rich is not installed
    USE_RICH = False

# Core Assistant Libraries
import speech_recognition as sr
import pyttsx3
import wikipedia

# LLM & Web Interaction
try:
    from groq import Groq
except ImportError:
    print("ERROR: Groq library not installed. Run 'pip install groq'. LLM features disabled.")
    Groq = None # Define as None if import fails
try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Selenium/BeautifulSoup/WebDriverManager not installed. Run 'pip install selenium beautifulsoup4 webdriver-manager lxml'. Web scraping disabled.")
    webdriver = None # Define as None if import fails

# ==============================================================================
# --- Configuration Loading ---
# ==============================================================================

def load_config(filename="config.ini"):
    """Loads configuration from an INI file."""
    if not os.path.exists(filename):
        print(f"FATAL ERROR: Configuration file '{filename}' not found.")
        print("Please create 'config.ini' with sections [General], [API_Keys], [LLM], [Scraping], [SpeechRecognition].")
        sys.exit(1)

    config = configparser.ConfigParser()
    try:
        config.read(filename)
        required_sections = ['General', 'API_Keys', 'LLM', 'Scraping', 'SpeechRecognition']
        if not all(section in config for section in required_sections):
             missing = [s for s in required_sections if s not in config]
             raise ValueError(f"Config file missing required sections: {missing}")
        return config
    except Exception as e:
        print(f"FATAL ERROR: Failed to read or parse config file '{filename}': {e}")
        sys.exit(1)

CONFIG = load_config()

# ==============================================================================
# --- Logging Setup ---
# ==============================================================================

def setup_logging(log_file="assistant.log"):
    """Configures logging to file and console."""
    log_level = logging.INFO # Console level
    log_format = "%(asctime)s - %(levelname)-8s - %(name)-12s - %(message)s"
    log_datefmt = "%Y-%m-%d %H:%M:%S"
    logger = logging.getLogger() # Get root logger
    logger.setLevel(logging.DEBUG) # Set root logger to lowest level

    # Basic formatter for file
    file_formatter = logging.Formatter(log_format, datefmt=log_datefmt)

    # Console handler (Rich or basic)
    if USE_RICH:
        console_handler = RichHandler(
            rich_tracebacks=True, markup=True, log_time_format="[%X]", level=log_level,
            omit_repeated_times=False # Show timestamp for every console message
        )
        # Use a simpler format for Rich console, letting Rich handle styling
        console_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(log_format, datefmt=log_datefmt))
        console_handler.setLevel(log_level)

    # File handler
    try:
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG) # Log DEBUG level and above to file
    except Exception as e:
        print(f"WARNING: Could not configure file logging to '{log_file}': {e}")
        file_handler = None

    # Clear existing handlers (if any, e.g., during reloads in some environments)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Add handlers
    logger.addHandler(console_handler)
    if file_handler:
        logger.addHandler(file_handler)

    # Suppress overly verbose logs from imported libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver.remote").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver.common").setLevel(logging.WARNING)
    logging.getLogger("webdriver_manager").setLevel(logging.ERROR) # Be quieter
    logging.getLogger("pyttsx3").setLevel(logging.WARNING)

setup_logging()
main_logger = logging.getLogger("AssistantCore") # Specific logger for core assistant logic
main_logger.info("-------------------- Assistant Starting Up --------------------")
main_logger.info(f"Using Rich console output: {USE_RICH}")

# ==============================================================================
# --- Global Constants & Variables from Config ---
# ==============================================================================
try:
    ASSISTANT_NAME = CONFIG.get('General', 'AssistantName', fallback="Assistant")
    USER_NAME = CONFIG.get('General', 'UserName', fallback="User")
    USER_HOBBY = CONFIG.get('General', 'UserHobby', fallback="exploring")
    DEVELOPER_NAME = CONFIG.get('General', 'DeveloperName', fallback="Developer")
    NOTES_FILE = CONFIG.get('General', 'NotesFile', fallback="notes.txt")

    WEATHER_API_KEY = CONFIG.get('API_Keys', 'OpenWeatherMap', fallback=None)
    GROQ_API_KEY = CONFIG.get('API_Keys', 'Groq', fallback=None)

    LLM_MODEL = CONFIG.get('LLM', 'Model', fallback="llama3-8b-8192")
    LLM_MAX_TOKENS = CONFIG.getint('LLM', 'MaxTokens', fallback=200)
    LLM_TEMPERATURE = CONFIG.getfloat('LLM', 'Temperature', fallback=0.7)

    SCRAPE_MAX_CHARS = CONFIG.getint('Scraping', 'MaxChars', fallback=6000)
    SELENIUM_TIMEOUT = CONFIG.getint('Scraping', 'SeleniumTimeout', fallback=15)
    RUN_SELENIUM_HEADLESS = CONFIG.getboolean('Scraping', 'RunHeadless', fallback=True)

    MIC_TIMEOUT = CONFIG.getint('SpeechRecognition', 'MicTimeout', fallback=5)
    PHRASE_LIMIT = CONFIG.getint('SpeechRecognition', 'PhraseLimit', fallback=10)
    PAUSE_THRESHOLD = CONFIG.getfloat('SpeechRecognition', 'PauseThreshold', fallback=0.8)

    main_logger.info(f"Configuration loaded successfully for user '{USER_NAME}'. Assistant Name: '{ASSISTANT_NAME}'.")

except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
     main_logger.error(f"Configuration Error in config.ini: {e}. Check file structure and values.", exc_info=True)
     # Attempt to use fallbacks where defined, but warn about missing critical keys
     if not WEATHER_API_KEY: main_logger.critical("OpenWeatherMap API Key is MISSING in config. Weather functionality disabled.")
     if not GROQ_API_KEY: main_logger.critical("Groq API Key is MISSING in config. LLM functionality disabled.")
     # Exit if critical keys are missing? Decide based on desired behavior. For now, just warn.

# Global state variables
tts_engine = None
llm_client = None
is_shutting_down = False
active_driver = None # Global reference to Selenium driver for cleanup

# ==============================================================================
# --- Initialization: TTS, LLM, Webdriver Check ---
# ==============================================================================
def initialize_tts():
    """Initializes the Text-to-Speech engine."""
    global tts_engine
    try:
        tts_engine = pyttsx3.init()
        # ... (Voice selection logic - same as before) ...
        voices = tts_engine.getProperty('voices')
        preferred_voice_id = None
        if len(voices) > 1: preferred_voice_id = voices[1].id # Default preference
        # Example: More specific preference check (adjust IDs/names for your system)
        # for voice in voices:
        #     if 'Zira' in voice.name or 'female' in voice.name.lower():
        #         preferred_voice_id = voice.id
        #         break
        if preferred_voice_id: tts_engine.setProperty('voice', preferred_voice_id)
        elif voices: tts_engine.setProperty('voice', voices[0].id)

        tts_engine.setProperty('rate', 180)
        main_logger.info("TTS Engine Initialized.")
    except Exception as e:
        main_logger.error(f"Failed to initialize TTS engine: {e}", exc_info=True)
        tts_engine = None

def initialize_llm():
    """Initializes the Groq LLM client."""
    global llm_client
    if not Groq: # Check if Groq class exists (import failed)
        main_logger.error("Groq library not available. LLM disabled.")
        return
    if not GROQ_API_KEY:
        main_logger.warning("Groq API key not found in config. LLM functionality disabled.")
        return
    try:
        llm_client = Groq(api_key=GROQ_API_KEY)
        # Optional: Quick test to verify API key
        # llm_client.models.list()
        main_logger.info(f"LLM Client Initialized (Model: {LLM_MODEL}).")
    except Exception as e:
        main_logger.error(f"Failed to initialize Groq client: {e}", exc_info=True)
        if "authentication" in str(e).lower():
            main_logger.critical("Groq authentication failed! Check API Key in config.ini.")
        llm_client = None

def check_webdriver():
    """Checks if Selenium/WebDriver can be initialized (light check)."""
    if not webdriver: # Check if Selenium imported
         main_logger.warning("Selenium library not available. Web scraping commands disabled.")
         return False
    try:
        # Check if chromedriver can be found/installed by webdriver-manager
        main_logger.info("Checking WebDriver availability...")
        driver_path = ChromeDriverManager().install()
        if not driver_path or not os.path.exists(driver_path):
             raise Exception("WebDriverManager failed to provide a valid driver path.")
        main_logger.info(f"WebDriver check successful (driver path: {driver_path})")
        return True
    except Exception as e:
        main_logger.error(f"WebDriver check failed: {e}", exc_info=True)
        main_logger.warning("Web scraping/summarization may fail. Ensure Chrome is installed and accessible.")
        return False

# Perform Initializations
initialize_tts()
initialize_llm()
can_scrape = check_webdriver() # Check if scraping is potentially possible

# ==============================================================================
# --- Helper Functions: Speak & Listen ---
# ==============================================================================
_speak_listen_logger = logging.getLogger("SpeakListen") # Logger for these functions

def speak(text):
    """Speaks the given text using TTS and logs it."""
    _speak_listen_logger.info(f"{ASSISTANT_NAME}: {text}") # Log even if TTS fails
    if tts_engine and not is_shutting_down:
        try:
            tts_engine.say(text)
            tts_engine.runAndWait()
        except RuntimeError as e:
            # This can happen if the engine is interrupted or in a bad state
             _speak_listen_logger.warning(f"TTS Runtime Error (possibly busy or interrupted): {e}")
             # Consider trying to re-initialize TTS here if it happens often
        except Exception as e:
            _speak_listen_logger.error(f"Speech synthesis error: {e}", exc_info=True)
    elif is_shutting_down:
         _speak_listen_logger.info("Speak skipped: Assistant shutting down.")
    elif not tts_engine:
         _speak_listen_logger.warning("Speak skipped: TTS engine unavailable.")

def listen():
    """Listens for command, handles errors, returns lowercase text or error code string."""
    if is_shutting_down: return "shutdown"

    r = sr.Recognizer()
    r.pause_threshold = PAUSE_THRESHOLD
    # r.dynamic_energy_threshold = True # Optional: Adjusts sensitivity to noise

    with sr.Microphone() as source:
        _speak_listen_logger.info(f"Listening... (Timeout: {MIC_TIMEOUT}s, Limit: {PHRASE_LIMIT}s)")
        try:
            # Adjust for ambient noise - crucial for accuracy
            r.adjust_for_ambient_noise(source, duration=0.7) # Slightly longer adjustment
        except Exception as e:
             _speak_listen_logger.warning(f"Could not adjust for ambient noise: {e}")

        # Listen for audio input
        try:
            audio = r.listen(source, timeout=MIC_TIMEOUT, phrase_time_limit=PHRASE_LIMIT)
        except sr.WaitTimeoutError:
            _speak_listen_logger.info("Timeout: No speech detected.")
            return "timeout" # Specific code for timeout
        except Exception as e:
            _speak_listen_logger.error(f"Audio capture failed: {e}", exc_info=True)
            return "audio_error" # Specific code for audio hardware issues

    # Recognize speech using Google Web Speech API
    try:
        _speak_listen_logger.info("Recognizing speech...")
        command = r.recognize_google(audio, language='en-us')
        _speak_listen_logger.info(f"You said: '{command}'")
        return command.lower() # Return recognized text in lowercase
    except sr.UnknownValueError:
        _speak_listen_logger.info("Recognition failed: Could not understand audio.")
        # speak("Sorry, I couldn't quite understand that.") # Optional feedback
        return "recognition_error" # Specific code for understanding failure
    except sr.RequestError as e:
        _speak_listen_logger.error(f"Recognition network error: {e}")
        # Avoid speaking here if network is down, might fail again
        # speak("Sorry, I'm having trouble connecting to the speech service.")
        return "network_error" # Specific code for network issues
    except Exception as e:
        _speak_listen_logger.error(f"Unexpected recognition error: {e}", exc_info=True)
        return "recognition_error" # Generic recognition failure

# ==============================================================================
# --- Core Functionality / Command Handlers ---
# ==============================================================================
_handler_logger = logging.getLogger("CmdHandlers") # Logger for command handlers

# --- Basic Info & Utilities ---
def handle_greeting(command_text):
    speak(f"Hello {USER_NAME}!")

def handle_status_check(command_text):
    speak("I'm operational and ready for commands.")

def handle_personal_info(command_text):
    # ... (Same logic as before, using speak() ) ...
    if "my name" in command_text or "who am i" in command_text: speak(f"You told me your name is {USER_NAME}.")
    elif "my hobby" in command_text or "what do i like" in command_text: speak(f"I believe your hobby is {USER_HOBBY}.")
    elif "made you" in command_text or "created you" in command_text or "developer" in command_text: speak(f"I was created by {DEVELOPER_NAME}.")
    elif "your name" in command_text: speak(f"My name is {ASSISTANT_NAME}.")
    else: handle_status_check(command_text) # Default to status if ambiguous

def handle_system_info(command_text):
    # ... (Same logic as before, using speak() and logging) ...
    speak("Getting current system status...")
    try:
        uname = platform.uname(); cpu = psutil.cpu_percent(interval=0.5); mem = psutil.virtual_memory()
        speak(f"System: {uname.system} {uname.release} ({uname.machine}). CPU: {cpu}%. Memory: {mem.percent}% used ({mem.available / (1024**3):.2f} GB free).")
    except Exception as e: _handler_logger.error("Failed to get system info", exc_info=True); speak("Sorry, couldn't retrieve system details.")

def handle_time(command_text):
    now = datetime.datetime.now()
    speak(f"The current time is {now.strftime('%I:%M %p')}.")

def handle_date(command_text):
    now = datetime.datetime.now()
    speak(f"Today's date is {now.strftime('%B %d, %Y')}.")

# --- External APIs & Services ---
def handle_weather(command_text):
    # ... (Improved weather handling logic - same as before) ...
    if not WEATHER_API_KEY: speak("Weather service unavailable: API key missing."); return
    city = None # Extract city logic...
    if "weather in " in command_text: city = command_text.split("weather in ")[-1].strip().rstrip('.?!')
    elif "weather for " in command_text: city = command_text.split("weather for ")[-1].strip().rstrip('.?!')
    if not city: speak("Which city's weather?"); return

    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {'q': city, 'appid': WEATHER_API_KEY, 'units': 'metric'}
    speak(f"Fetching weather for {city.title()}..."); _handler_logger.info(f"Requesting weather: {city}")
    try: # API call + error handling...
        response = requests.get(base_url, params=params, timeout=10); response.raise_for_status()
        data = response.json()
        if data.get("cod") == 200: # Report logic...
             main=data["main"]; weather=data["weather"][0]; wind=data.get("wind",{})
             report = (f"In {data['name']}: {weather['description']}. Temp: {main['temp']:.1f}°C (feels like {main['feels_like']:.1f}°C). Humidity: {main['humidity']}%.")
             if 'speed' in wind: report += f" Wind: {wind['speed']:.1f} m/s."
             speak(report)
        elif data.get("cod") == "404": speak(f"Sorry, couldn't find weather data for {city.title()}.")
        else: message = data.get("message", "API error"); _handler_logger.error(f"OWM API Error {data.get('cod')}: {message}"); speak(f"Weather service error: {message}")
    except requests.exceptions.Timeout: _handler_logger.warning("Weather request timed out."); speak("Weather service timed out.")
    except requests.exceptions.HTTPError as e: _handler_logger.error(f"HTTP Error fetching weather: {e}", exc_info=True); speak(f"Failed to retrieve weather (HTTP {e.response.status_code}). Check API key if 401.")
    except requests.exceptions.RequestException as e: _handler_logger.error(f"Network Error fetching weather: {e}", exc_info=True); speak("Couldn't connect to weather service.")
    except Exception as e: _handler_logger.exception("Unexpected weather error"); speak("An unexpected error occurred getting the weather.")


def handle_wikipedia(command_text):
    # ... (Improved Wikipedia logic - same as before) ...
    topic = None # Extract topic logic...
    if "wikipedia" in command_text: topic = command_text.split("wikipedia")[-1].replace("about", "").replace("search for", "").strip()
    elif "tell me about " in command_text: topic = command_text.split("tell me about ")[-1].strip()
    if not topic: speak("What topic for Wikipedia?"); return

    speak(f"Searching Wikipedia for {topic}..."); _handler_logger.info(f"Requesting Wikipedia: '{topic}'")
    try: # API call + error handling...
        wikipedia.set_lang("en")
        summary = wikipedia.summary(topic, sentences=2, auto_suggest=True, redirect=True) # Allow redirects
        speak(summary)
    except wikipedia.exceptions.PageError: _handler_logger.info(f"Wiki PageError: '{topic}'"); speak(f"Sorry, couldn't find a Wikipedia page for '{topic}'.")
    except wikipedia.exceptions.DisambiguationError as e: _handler_logger.info(f"Wiki Disambiguation: '{topic}'"); speak(f"'{topic}' could mean several things (like {', '.join(e.options[:3])}). Please be more specific.")
    except requests.exceptions.RequestException as e: _handler_logger.error(f"Network Error accessing Wiki: {e}", exc_info=True); speak("Sorry, couldn't connect to Wikipedia.")
    except Exception as e: _handler_logger.exception("Unexpected Wikipedia error"); speak("An unexpected error occurred searching Wikipedia.")

def handle_joke(command_text):
    # ... (Joke logic with pause - same as before) ...
    speak("Okay, finding a joke..."); url = "https://v2.jokeapi.dev/joke/Any?safe-mode"
    _handler_logger.info("Requesting joke from JokeAPI")
    try: # API call + error handling...
        response = requests.get(url, timeout=10); response.raise_for_status(); data = response.json()
        if data.get("error"): _handler_logger.error(f"JokeAPI Error: {data.get('message')}"); speak("Sorry, couldn't fetch a joke (API error)."); return
        if data["type"] == "single": speak(data["joke"])
        elif data["type"] == "twopart": speak(data['setup']); time.sleep(1.5); speak(data['delivery'])
        else: speak("Found a joke, but its format is weird.")
    except requests.exceptions.RequestException as e: _handler_logger.error(f"Network Error fetching joke: {e}", exc_info=True); speak("Sorry, couldn't connect to joke service.")
    except Exception as e: _handler_logger.exception("Failed to get/process joke"); speak("Something went wrong getting a joke.")

# --- Local Actions & Web Interaction ---
def handle_web_search(command_text):
    # ... (Same logic, use speak() and logging) ...
    term = command_text.replace("search for", "", 1).strip() # Remove only first instance
    if not term: speak("What should I search the web for?"); return
    url = f"https://www.google.com/search?q={requests.utils.quote(term)}"
    speak(f"Okay, opening Google search for '{term}'.")
    _handler_logger.info(f"Opening web browser for search: {term}")
    try: webbrowser.open(url)
    except Exception as e: _handler_logger.error(f"Failed to open web browser: {e}", exc_info=True); speak("Sorry, couldn't open the web browser.")

def _open_application_internal(app_name_normalized):
    """Internal logic to open apps (returns True on success command execution, False otherwise)."""
    # ... (Improved internal logic with shutil.which - same as before) ...
    system = platform.system(); cmd = None; success = False
    _handler_logger.info(f"Attempting to open '{app_name_normalized}' on {system}")
    # Define commands based on normalized name and OS...
    if app_name_normalized == 'notepad':
        if system == "Windows": cmd = "start notepad"
        elif system == "Darwin": cmd = "open -a TextEdit"
        else: # Linux
             cmd_options = ["gedit", "kate", "mousepad", "pluma", "xed"] # GUI first
             terminal_cmd = "nano" # Terminal fallback
             found_cmd = next((f"{c} &" for c in cmd_options if shutil.which(c)), None)
             cmd = found_cmd if found_cmd else terminal_cmd if shutil.which(terminal_cmd) else None
    elif app_name_normalized == 'calculator':
        if system == "Windows": cmd = "start calc"
        elif system == "Darwin": cmd = "open -a Calculator"
        else: # Linux
            cmd_options = ["gnome-calculator", "kcalc", "galculator"]
            terminal_cmd = "bc"
            found_cmd = next((f"{c} &" for c in cmd_options if shutil.which(c)), None)
            cmd = found_cmd if found_cmd else terminal_cmd if shutil.which(terminal_cmd) else None

    # Execute the command if found
    if cmd:
        try:
            exit_code = os.system(cmd)
            if exit_code == 0: _handler_logger.info(f"Successfully executed: {cmd}"); success = True
            else: _handler_logger.warning(f"Command failed (Code {exit_code}): {cmd}")
        except Exception as e: _handler_logger.error(f"Exception running command '{cmd}': {e}", exc_info=True)
    else: _handler_logger.warning(f"No command found for '{app_name_normalized}' on {system}")
    return success

def handle_open(command_text):
    """Handles 'open X' for websites and local apps."""
    # ... (Improved open logic - same as before) ...
    target = command_text.replace("open", "", 1).strip().lower(); opened = False; url = None
    if not target: speak("What should I open?"); return
    _handler_logger.info(f"Handling 'open' for target: '{target}'")
    # Website check...
    if target == 'google': url = "https://www.google.com"
    elif target == 'youtube': url = "https://www.youtube.com"
    # Add more...
    if url: # Handle URL opening...
        speak(f"Opening {target.capitalize()} in browser."); _handler_logger.info(f"Opening URL: {url}")
        try: webbrowser.open(url); opened = True
        except Exception as e: _handler_logger.error(f"Failed to open URL {url}: {e}", exc_info=True); speak(f"Sorry, couldn't open {target.capitalize()}.")
    else: # Try local app...
        app_name_normalized = target.replace(" ","") # Simple normalization
        if app_name_normalized in ['notepad', 'texteditor', 'editor']: app_name_normalized = 'notepad'
        elif app_name_normalized == 'calc': app_name_normalized = 'calculator'
        speak(f"Trying to open {target}...")
        opened = _open_application_internal(app_name_normalized)
        if not opened and not llm_client: # Only report specific failure if LLM isn't fallback
             speak(f"Sorry, couldn't find or open '{target}' on your system.")
        elif opened:
             _handler_logger.info(f"Successfully initiated opening of '{target}'.")
        else: # Not opened, but LLM might handle it
             _handler_logger.info(f"Direct open failed for '{target}', may fall back to LLM.")
    # 'processed' flag is implicit by matching in COMMAND_MAP

def handle_search_scrape_summarize(command_text):
    """Handler for 'search about X' using Selenium and LLM."""
    global active_driver
    if not webdriver or not can_scrape:
        speak("Sorry, the web browsing module is not available or failed initialization. I can't perform this search.")
        return

    keyword = command_text.replace("search about", "", 1).strip()
    if not keyword:
        speak("What keyword should I search about and summarize?"); return

    speak(f"Okay, searching online for '{keyword}' to summarize the first result. This might take a minute...")
    _handler_logger.info(f"Starting search/scrape/summarize for: '{keyword}'")
    driver = None # Local variable for this instance

    try:
        # --- Setup WebDriver ---
        _handler_logger.info("Setting up Selenium WebDriver...")
        options = webdriver.ChromeOptions()
        if RUN_SELENIUM_HEADLESS: options.add_argument("--headless")
        options.add_argument("--disable-gpu"); options.add_argument("--window-size=1920,1080")
        options.add_argument("--log-level=3"); options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--no-sandbox'); options.add_argument('--disable-dev-shm-usage') # Common headless/docker fixes

        try:
            driver_path = ChromeDriverManager().install()
            service = ChromeService(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            active_driver = driver # Store globally for cleanup
            driver.implicitly_wait(8) # Slightly longer implicit wait
            _handler_logger.info("WebDriver initialized.")
        except WebDriverException as e:
            _handler_logger.error(f"WebDriver Initialization Failed: {e}", exc_info=True)
            speak("Sorry, I couldn't start the web browser tool. Ensure Chrome is installed and accessible.")
            active_driver = None # Clear global ref if failed
            return

        # --- Google Search & Link Finding ---
        _handler_logger.info(f"Navigating Google & searching for: {keyword}")
        driver.get("https://www.google.com")
        # Cookie consent (more robust)
        try:
            wait = WebDriverWait(driver, 5)
            consent_xpath = "//button[.//div[contains(text(), 'Accept all')]] | //button[.//div[contains(text(), 'Reject all')]] | //button[contains(., 'Accept all')] | //button[contains(., 'Reject all')]"
            consent_button = wait.until(EC.element_to_be_clickable((By.XPATH, consent_xpath)))
            consent_button.click(); _handler_logger.info("Clicked cookie consent button."); time.sleep(0.5)
        except TimeoutException: _handler_logger.info("Cookie consent button not found/clicked (Timeout).")
        except Exception as e: _handler_logger.warning(f"Minor error clicking cookie button: {e}")

        search_box = WebDriverWait(driver, SELENIUM_TIMEOUT).until(EC.presence_of_element_located((By.NAME, "q")))
        search_box.send_keys(keyword); search_box.send_keys(Keys.RETURN)
        _handler_logger.info("Search submitted. Waiting for results...")

        first_link_url = None # Find link logic... (Fragile!)
        try:
            results_container = WebDriverWait(driver, SELENIUM_TIMEOUT).until(EC.presence_of_element_located((By.ID, "search")))
            _handler_logger.info("Search results loaded.")
            # Refined Selector - PRIORITIZE links inside divs commonly used for organic results
            # This still needs maintenance if Google changes layouts often
            potential_results_divs = results_container.find_elements(By.CSS_SELECTOR, "div.g, div.kvH3mc") # Common result block classes
            for res_div in potential_results_divs:
                 try:
                     link_element = res_div.find_element(By.CSS_SELECTOR, "a[href][data-ved]") # Links with tracking data are often results
                     h3_element = res_div.find_element(By.TAG_NAME, "h3") # Look for heading within the block
                     url = link_element.get_attribute('href')

                     # Filter out ads, internal google links, etc.
                     if url and url.startswith('http') and \
                        'google.com/' not in url and '/search?q=' not in url and \
                        'webcache.googleusercontent.com' not in url and \
                        h3_element and h3_element.text and h3_element.is_displayed():
                            first_link_url = url
                            _handler_logger.info(f"Found potential result link: {first_link_url} (Title: {h3_element.text})")
                            break # Found one, stop looking
                 except Exception: continue # Ignore divs that don't match the structure

            if not first_link_url: # If the refined search failed, try the broader previous approach
                 _handler_logger.warning("Refined link search failed, trying broader selector.")
                 links = results_container.find_elements(By.CSS_SELECTOR, "div#search div.g a[href]")
                 for link in links: # Broader fallback selector (less reliable)
                     url = link.get_attribute('href')
                     if url and url.startswith('http') and 'google.com' not in url and 'webcache' not in url:
                          try:
                               h3 = link.find_element(By.XPATH, ".//h3")
                               if h3 and h3.text: first_link_url = url; _handler_logger.info(f"Found fallback link: {first_link_url}"); break
                          except: continue

            if not first_link_url:
                _handler_logger.error("Failed to identify a suitable first result link.")
                speak(f"Sorry, I couldn't reliably find the first search result link for '{keyword}'.")
                return
        except TimeoutException: _handler_logger.error("Timeout waiting for Google search results container."); speak("Sorry, timed out waiting for search results.") ; return
        except Exception as e: _handler_logger.error(f"Error finding search results: {e}", exc_info=True); speak("Sorry, error processing search results."); return

        # --- Navigate, Scrape, Summarize ---
        _handler_logger.info(f"Navigating to: {first_link_url}")
        driver.get(first_link_url)
        try: # Wait for page load (improved condition)
             WebDriverWait(driver, SELENIUM_TIMEOUT).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        except TimeoutException: _handler_logger.warning(f"Timeout waiting for page load state on {first_link_url}. Proceeding anyway.")
        _handler_logger.info("Target page loaded. Scraping content...")

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'lxml')
        # Text extraction logic (decompose unwanted, find main, fallback) - same as before
        for element in soup(["script", "style", "header", "footer", "nav", "aside", "form", "button", "iframe", "img", "figure"]): element.decompose()
        main_content = soup.find('article') or soup.find('main') or soup.find(role='main') or soup.find(id=re.compile(r'content|main', re.I)) or soup.find(class_=re.compile(r'content|post|article|body', re.I))
        if main_content: text = main_content.get_text(separator='\n', strip=True); _handler_logger.info(f"Extracted text from primary container ({len(text)} chars).")
        else:
             paragraphs = soup.find_all('p'); text = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]); _handler_logger.info(f"Extracted text from <p> tags ({len(text)} chars).")
             if not text: text = soup.body.get_text(separator='\n', strip=True) if soup.body else ""; _handler_logger.info(f"Extracted text from <body> (fallback, {len(text)} chars).")
        text = re.sub(r'\n\s*\n', '\n\n', text).strip() # Clean whitespace

        if not text or len(text) < 100: # Check for minimal meaningful content
            _handler_logger.warning(f"Failed to extract sufficient text content from {first_link_url}")
            speak("Sorry, I couldn't extract enough readable content from that web page to summarize.")
            return

        # Summarize using LLM (pass context)
        _handler_logger.info(f"Sending {len(text)} chars to LLM for summarization...")
        summary_prompt = f"Please provide a concise summary (around 2-4 sentences) of the main points from the following text extracted from a webpage about '{keyword}':"
        summary = handle_llm_interaction(summary_prompt, context_text=text) # Use dedicated LLM handler

        # Check if LLM returned an error message
        if "error" in summary.lower() or "failed" in summary.lower() or "unavailable" in summary.lower():
             speak(f"I got the content, but failed to summarize it: {summary}")
        else:
             speak(f"Here's a summary from the first search result I found for '{keyword}':\n{summary}")

    except WebDriverException as e:
         _handler_logger.error(f"Selenium WebDriver Error during scrape: {e}", exc_info=True)
         speak(f"Sorry, a browser automation error occurred while processing '{keyword}'.")
    except Exception as e:
        _handler_logger.exception(f"Unexpected error during search/scrape/summarize for '{keyword}'")
        speak(f"Sorry, an unexpected error occurred while trying to search and summarize '{keyword}'.")
    finally: # Ensure driver cleanup
        if driver:
            try:
                driver.quit(); _handler_logger.info("WebDriver closed.")
            except Exception as e: _handler_logger.warning(f"Error closing WebDriver: {e}")
        active_driver = None # Clear global reference

# --- NEW: Take Note Feature ---
# --- NEW: Take Note Feature ---
def handle_take_note(command_text):
    """Appends the spoken text (after 'take note') to the notes file."""
    # Extract content provided immediately after "take note"
    note_content = command_text.replace("take note", "", 1).strip()

    # If content wasn't provided with the initial command, ask and listen again
    if not note_content:
        speak("What note should I take?")
        _handler_logger.info("Listening again specifically for note content...")
        # Call listen() again to capture just the note
        note_content = listen()

        # Check if listening failed, timed out, or returned no actual content
        listen_errors = ["timeout", "audio_error", "recognition_error", "network_error", "shutdown"]
        if note_content in listen_errors or not note_content.strip(): # Check if empty after stripping
            speak("Okay, cancelling note.")
            _handler_logger.warning(f"Note cancelled. Reason: Listen error ('{note_content}') or empty content.")
            return # Exit the function without saving

    # Proceed only if we have valid note_content (either from the initial command or the second listen)
    speak(f"Okay, noting down: '{note_content}'")
    try:
        # Use NOTES_FILE defined globally from config
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {note_content}\n")
        _handler_logger.info(f"Note successfully appended to {NOTES_FILE}")
    except Exception as e:
        _handler_logger.error(f"Failed to write to notes file '{NOTES_FILE}': {e}", exc_info=True)
        speak(f"Sorry, I encountered an error trying to save the note.")

    speak(f"Okay, noting down: '{note_content}'")
    try:
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {note_content}\n")
        _handler_logger.info(f"Note appended to {NOTES_FILE}")
    except Exception as e:
        _handler_logger.error(f"Failed to write to notes file '{NOTES_FILE}': {e}", exc_info=True)
        speak(f"Sorry, I couldn't save the note due to an error.")

# --- LLM Interaction Handler ---
def handle_llm_interaction(command_text, context_text=None):
    """Handles generic commands by forwarding to LLM, optionally with context."""
    if not llm_client:
        # Only speak error if it wasn't a specific known command that failed
        # (Avoids double error messages)
        # We rely on the main loop's final fallback for this
        _handler_logger.warning("LLM interaction requested but client unavailable.")
        return "Sorry, my chat features are currently offline." # Return error string

    # Don't send error codes as prompts
    if command_text in ["timeout", "audio_error", "recognition_error", "network_error"]:
        return "I didn't get a clear prompt for the chat."

    # Prepare prompt, potentially including context
    final_prompt = command_text
    prompt_desc = f"Sending prompt ({len(command_text)} chars) to LLM..."
    if context_text:
        # Truncate context if needed
        original_len = len(context_text)
        if original_len > SCRAPE_MAX_CHARS:
             context_text = context_text[:SCRAPE_MAX_CHARS] + "... [truncated]"
             _handler_logger.info(f"Truncated context text from {original_len} to {len(context_text)} chars.")
        final_prompt = f"{command_text}\n\n### Context Provided:\n{context_text}"
        prompt_desc = f"Sending prompt with context ({len(final_prompt)} chars) to LLM..."

    _handler_logger.info(prompt_desc)
    # speak("Okay, let me think about that...") # Optional feedback

    try:
        messages = [
            {"role": "system", "content": f"You are {ASSISTANT_NAME}, a helpful AI assistant for {USER_NAME}. Keep responses concise."},
            {"role": "user", "content": final_prompt}
        ]
        chat_completion = llm_client.chat.completions.create(
            messages=messages, model=LLM_MODEL, temperature=LLM_TEMPERATURE, max_tokens=LLM_MAX_TOKENS
        )
        response_content = chat_completion.choices[0].message.content.strip()
        _handler_logger.info(f"LLM Response received ({chat_completion.usage.completion_tokens} tokens)")
        return response_content
    except Exception as e:
        _handler_logger.error(f"LLM API communication failed: {e}", exc_info=True)
        # Return specific user-friendly error based on exception type if possible
        error_str = str(e).lower()
        if "authentication" in error_str: return "LLM authentication failed. Check API key."
        elif "rate limit" in error_str: return "LLM chat service is busy. Try again shortly."
        elif "quota" in error_str: return "LLM usage limit reached."
        elif "connection" in error_str or "network" in error_str: return "Couldn't connect to LLM service."
        else: return "Sorry, an error occurred processing the chat request."

# --- Exit Handler ---
def handle_exit(command_text=None):
    """Initiates the shutdown sequence."""
    global is_shutting_down
    if not is_shutting_down: # Prevent multiple calls
        is_shutting_down = True
        main_logger.info("Shutdown initiated by command or signal.")
        speak(f"Goodbye {USER_NAME}! Shutting down.")
        # Give TTS time to finish if possible
        time.sleep(1)
    # Actual cleanup happens in the main loop's finally block or signal handler

# ==============================================================================
# --- Command Mapping & Dispatch ---
# ==============================================================================

# Dictionary mapping trigger phrases/keywords to handler functions
# Order can matter if commands overlap (e.g., 'search about' vs 'search for')
# More specific commands should generally come first.
COMMAND_MAP = {
    "hello": handle_greeting,
    "hi": handle_greeting,
    "hey": handle_greeting,
    "greetings": handle_greeting,
    "how are you": handle_status_check,
    "status": handle_status_check,
    "what is my name": handle_personal_info,
    "who am i": handle_personal_info,
    "my hobby": handle_personal_info,
    "what do i like": handle_personal_info,
    "who made you": handle_personal_info,
    "who created you": handle_personal_info,
    "your developer": handle_personal_info,
    "your name": handle_personal_info,
    "system information": handle_system_info,
    "system status": handle_system_info,
    "what time is it": handle_time,
    "the time": handle_time,
    "what's the date": handle_date,
    "today's date": handle_date,
    "weather in": handle_weather, # Trigger requires city after
    "weather for": handle_weather, # Alternative trigger
    "wikipedia": handle_wikipedia, # Trigger requires topic after
    "tell me about": handle_wikipedia, # Alternative trigger
    "tell me a joke": handle_joke,
    "say a joke": handle_joke,
    "search about": handle_search_scrape_summarize, # Specific scrape/summarize command
    "search for": handle_web_search, # Simple browser search
    "open": handle_open, # Handles 'open google', 'open notepad', etc.
    "take note": handle_take_note, # New note command
    "exit": handle_exit,
    "quit": handle_exit,
    "goodbye": handle_exit,
    "bye": handle_exit,
    "turn off": handle_exit,
    "shut down": handle_exit,
}

def dispatch_command(command_text):
    """Finds and executes the appropriate handler for the command."""
    if not command_text or command_text in ["timeout", "audio_error", "recognition_error", "network_error", "shutdown"]:
        return False # Not a valid command to process

    # Check for exact or partial keyword matches from the map
    processed = False
    for trigger, handler in COMMAND_MAP.items():
        if command_text.startswith(trigger):
            try:
                main_logger.info(f"Dispatching command '{command_text}' to handler: {handler.__name__}")
                handler(command_text) # Pass the full command text to the handler
                processed = True
                break # Stop checking once a handler is found and executed
            except Exception as e:
                 main_logger.error(f"Error executing handler {handler.__name__} for command '{command_text}'", exc_info=True)
                 speak("Sorry, I encountered an error trying to process that command.")
                 processed = True # Mark as processed even if error occurred to prevent LLM fallback
                 break

    # If no specific command was processed, fall back to LLM
    if not processed and llm_client:
        main_logger.info(f"No specific handler found for '{command_text}'. Forwarding to LLM.")
        llm_response = handle_llm_interaction(command_text)
        speak(llm_response)
        processed = True # Mark LLM interaction as processed

    # If still not processed (no specific command, LLM disabled/failed)
    elif not processed:
        main_logger.warning(f"Command not recognized and no LLM fallback: '{command_text}'")
        speak("Sorry, I don't understand that command, and my chat features are offline.")
        processed = True # Mark as processed to prevent looping issues

    return processed

# ==============================================================================
# --- Signal Handling for Graceful Exit ---
# ==============================================================================

def signal_handler(sig, frame):
    """Handles Ctrl+C or termination signals."""
    main_logger.warning(f"Received signal {sig}. Initiating graceful shutdown...")
    handle_exit() # Trigger the shutdown sequence

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler) # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # Termination signal

# ==============================================================================
# --- Main Execution Loop ---
# ==============================================================================
def main():
    """Main loop for the assistant."""
    global is_shutting_down, active_driver

    # Initial greeting
    try:
        hour = datetime.datetime.now().hour
        if 0 <= hour < 12: greeting = f"Good morning {USER_NAME}!"
        elif 12 <= hour < 18: greeting = f"Good afternoon {USER_NAME}!"
        else: greeting = f"Good evening {USER_NAME}!"
        speak(f"{greeting} This is {ASSISTANT_NAME}. How can I help?")
    except Exception as e:
         main_logger.error(f"Error during initial greeting: {e}")
         # Continue running even if greeting fails

    # Main listening loop
    while not is_shutting_down:
        command = listen()

        if command == "shutdown": # Check if shutdown initiated during listen
            break

        dispatch_command(command)

        # Small delay to prevent tight looping on errors
        if command in ["timeout", "audio_error", "recognition_error", "network_error"]:
            time.sleep(0.5)

    # --- Cleanup Actions ---
    main_logger.info("Exited main loop. Performing final cleanup...")

    # Close Selenium WebDriver if active
    if active_driver:
        main_logger.info("Closing active Selenium WebDriver...")
        try:
            active_driver.quit()
            main_logger.info("WebDriver closed successfully.")
        except Exception as e:
            main_logger.warning(f"Error closing WebDriver during shutdown: {e}")
        finally:
             active_driver = None

    # Optional: Stop TTS engine (can sometimes hang, so often omitted)
    # if tts_engine:
    #     try: tts_engine.stop()
    #     except Exception as e: main_logger.warning(f"Error stopping TTS engine: {e}")

    main_logger.info("-------------------- Assistant Shutdown Complete --------------------")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # This handles Ctrl+C if the signal handler didn't catch it fast enough
        main_logger.warning("KeyboardInterrupt received. Shutting down.")
        handle_exit()
    except Exception as e:
        # Catch any unexpected errors in the main function itself
        main_logger.critical("An unhandled exception occurred in the main loop!", exc_info=True)
        # Attempt cleanup even on critical error
        if active_driver:
            try: active_driver.quit()
            except: pass # Ignore errors during emergency cleanup
    finally:
        logging.shutdown() # Ensure all log handlers are flushed and closed
        print("\nProgram exited.")