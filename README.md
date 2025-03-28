# Byte 🗣️✨: Your Advanced Personal AI Assistant

[![Made in Bangladesh](https://img.shields.io/badge/Made%20in-Bangladesh%20%F0%9F%87%A7%F0%9F%87%A9-007042?style=flat-square)](https://en.wikipedia.org/wiki/Bangladesh)

Welcome to **Byte**, an advanced, voice-controlled personal AI assistant built with Python. Inspired by systems like J.A.R.V.I.S., Byte aims to provide helpful information, perform tasks, and engage in conversation, all through voice commands.

This project is proudly **Made in Bangladesh 🇧🇩**, showcasing the potential of local talent in AI and software development.

Byte is designed to be configurable and extensible, leveraging powerful libraries and free APIs for a wide range of capabilities.

---

## 🚀 Features

*   **🗣️ Voice Interaction:** Listen to voice commands and respond with synthesized speech (Text-to-Speech).
*   **🧠 Conversational AI:** Engage in general conversation and answer questions using the powerful Groq API (leveraging models like Llama 3).
*   **⚙️ System Awareness:** Reports system information like OS, CPU usage, and memory usage.
*   **🕰️ Time & Date:** Tells the current time and date.
*   **☁️ Weather Updates:** Fetches and reports current weather information for any city using OpenWeatherMap.
*   **📚 Wikipedia Search:** Looks up topics on Wikipedia and reads a concise summary.
*   **😂 Jokes:** Tells jokes fetched from a dedicated joke API.
*   **🌐 Web Interaction:**
    *   Performs Google searches in your default browser.
    *   Opens specific websites (Google, YouTube, GitHub, Gmail).
*   **🖱️ Web Scraping & Summarization:** Performs a Google search for a keyword, automatically navigates to the first relevant result, scrapes its content, and provides an AI-generated summary (Experimental & requires maintenance).
*   **💻 Application Launch:** Opens common local applications like Notepad/TextEdit and Calculator (cross-platform support).
*   **📝 Note Taking:** Allows you to dictate notes which are saved to a local text file (`notes.txt`) with timestamps.
*   **🔧 Configuration:** Easy setup via an external `config.ini` file for API keys and preferences.
*   **📄 Logging:** Detailed logging to `assistant.log` for diagnostics and debugging.
*   **🇧🇩 Made in Bangladesh:** Developed with passion in Bangladesh!

---

## 🛠️ Tech Stack

*   **Core:** Python 3.x
*   **Speech:** `SpeechRecognition`, `PyAudio`, `pyttsx3`
*   **LLM:** `groq` (for fast LLM inference via Groq Cloud)
*   **Web Scraping/Automation:** `selenium`, `beautifulsoup4`, `webdriver-manager`, `lxml`
*   **APIs:** `requests` (for Weather & Jokes), `wikipedia-api`
*   **System Info:** `psutil`
*   **Configuration:** `configparser`
*   **Logging:** `logging` (built-in)
*   **(Optional Console UI):** `rich`

---

## ⚙️ Setup & Installation

Follow these steps to get Byte running on your local machine:

1.  **Clone the Repository (If applicable):**
    ```bash
    https://github.com/redwans324/byte-asistent.git
    cd byte-asistent
    ```
    *(If you just have the files, ensure they are all in one directory)*

2.  **Create/Verify `config.ini`:**
    *   Make sure you have a `config.ini` file in the project directory.
    *   **Crucially, open `config.ini` and replace the placeholder API keys** in the `[API_Keys]` section with your actual keys from [OpenWeatherMap](https://openweathermap.org/) and [Groq](https://console.groq.com/).
    *   Adjust `UserName`, `AssistantName`, and other settings in `[General]` as desired.

3.  **Install Dependencies:**
    *   Ensure you have Python 3.8+ installed.
    *   Install all required libraries using the `requirements.txt` file:
        ```bash
        pip install -r requirements.txt
        ```
    *   **Note on `PyAudio`:** Installation can sometimes be tricky. If you encounter errors, search for specific installation instructions for `PyAudio` on your operating system (Windows/macOS/Linux). You might need to install system dependencies first (like `portaudio`).

4.  **Install Google Chrome:** The web scraping feature uses Selenium with ChromeDriver. Ensure you have Google Chrome installed on your system. `webdriver-manager` will attempt to download the correct ChromeDriver automatically.

---

## 🔧 Configuration (`config.ini`)

All major settings are managed in the `config.ini` file:

*   **`[General]`**: Customize names (`AssistantName`, `UserName`), developer name, and the notes filename.
*   **`[API_Keys]`**: **Mandatory** section for your OpenWeatherMap and Groq API keys. **Keep this file secure!**
*   **`[LLM]`**: Choose the Groq language model, set token limits, and adjust creativity (`Temperature`).
*   **`[Scraping]`**: Control Selenium behavior (headless mode, timeouts) and context length for summarization.
*   **`[SpeechRecognition]`**: Fine-tune microphone timeouts and sensitivity.

---

## ▶️ Usage

1.  **Navigate to Directory:** Open your terminal or command prompt and go to the project directory (`WALTON/Desktop/codes/`).
2.  **Run the Script:**
    ```bash
    python advanced_assistant.py
    ```
    *(Replace `advanced_assistant.py` with your actual script filename if different)*
3.  **Wait for Initialization:** The assistant will print status messages and log to `assistant.log`. It will greet you when ready.
4.  **Speak Commands:** When you see "Listening..." in the console, speak your command clearly.

**Example Commands:**

*   "Hello Byte"
*   "What time is it?"
*   "What's today's date?"
*   "What is my name?" / "Who am I?"
*   "System information"
*   "Weather in Dhaka" / "Weather for London"
*   "Wikipedia about Python programming language" / "Tell me about the Eiffel Tower"
*   "Tell me a joke"
*   "Search for best Python tutorials"
*   "Open YouTube" / "Open Notepad" / "Open Calculator"
*   **"Search about the history of Bangladesh"** (Triggers web scraping & summarization)
*   **"Take note meeting scheduled for 3 PM"** (Saves the note)
*   Ask general questions (e.g., "Explain quantum computing briefly", "Suggest a good book") - these use the Groq LLM.
*   "Goodbye" / "Exit" / "Shut down"

---

## 📝 Logging & Notes

*   **Logs:** Detailed operation logs, warnings, and errors are saved in `assistant.log`. Check this file if you encounter issues.
*   **Notes:** Notes captured using the "take note" command are appended to the file specified in `config.ini` (default: `notes.txt`).

---

## 📄 License

*(**Developer Note:** Please choose a license like MIT, Apache 2.0, or GPLv3 and replace this section)*

This project is licensed under the [**mit laicense** License](LICENSE). Please see the `LICENSE.md` file for details.

---

## 🙏 Acknowledgements

*   Inspired by conversational AI concepts.
*   Uses fantastic open-source libraries and free APIs.
*   Developed with ❤️ in **Bangladesh** 🇧🇩.

---

*Feel free to contact [https://github.com/redwans324/] for questions or feedback.*
