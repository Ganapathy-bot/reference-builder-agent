# Reference Desk

Evidence-first reference lookup and citation formatting using Crossref, OpenAlex, DataCite, PubMed, Open Library, and publisher metadata.

## Run locally

```powershell
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

The FastAPI interface is also available with `python -m uvicorn app.main:app --app-dir .`.

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, choose **Create app** and connect `streamlit_app.py` from the repository's `main` branch.
3. Add `BIBLIO_MAILTO` in the app's secrets/settings if you want scholarly API requests to use a contact email.

The SQLite library is local to the running instance. Streamlit Community Cloud may reset local files when the app restarts.