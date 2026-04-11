# JM IDS Checker

Validates IFC files against IDS rule sets. Exports failures as BCF.

## Quick start

```bash
pip install -r requirements.txt
mkdir ids_files
# drop your .ids files into ids_files/
streamlit run app.py
```

## Raspberry Pi 5

```bash
chmod +x setup_pi.sh
./setup_pi.sh
source .venv/bin/activate
streamlit run app.py --server.address 0.0.0.0
```

Access from any device on your network at `http://<pi-ip>:8501`.

## File structure

```
jm-ids-checker/
├── app.py                  # Streamlit app
├── requirements.txt
├── setup_pi.sh             # Pi setup script
├── .streamlit/config.toml  # 300MB upload limit
└── ids_files/              # Drop .ids files here
```
