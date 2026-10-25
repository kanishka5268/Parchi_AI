"""
Parchi AI Entrypoint.
Run the web application with:
    streamlit run app.py
or:
    python main.py
"""
import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
