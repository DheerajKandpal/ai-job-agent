import os
from dataclasses import dataclass
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "AI Job Application Agent"
APP_SUBTITLE = "Analyze job fit and generate tailored outputs"
REQUEST_TIMEOUT = 60


@dataclass(frozen=True)
class UIConfig:
    backend_url: str
    api_key: str


def load_ui_config() -> UIConfig:
    backend_url = (os.getenv("BACKEND_URL") or "").strip()
    api_key = (os.getenv("API_KEY") or "").strip()
    if not backend_url:
        raise ValueError("BACKEND_URL is missing. Add it to your .env file.")
    if not api_key:
        raise ValueError("API_KEY is missing. Add it to your .env file.")
    return UIConfig(backend_url=backend_url.rstrip("/"), api_key=api_key)


def auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def call_backend(
    config: UIConfig,
    endpoint: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.post(
            f"{config.backend_url}{endpoint}",
            headers=auth_headers(config.api_key),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return None, "Could not connect to backend. Please verify BACKEND_URL and server status."

    if response.status_code in {401, 403}:
        return None, "Authentication failed. Please check API_KEY."
    if response.status_code >= 500:
        return None, "Backend server error. Please try again shortly."
    if not response.ok:
        return None, f"Request failed ({response.status_code})."

    try:
        return response.json(), None
    except ValueError:
        return None, "Backend returned an invalid response format."


def initialize_state() -> None:
    defaults = {
        "busy": False,
        "trigger_run": False,
        "match_result": None,
        "tailor_result": None,
        "cover_letter_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_header() -> None:
    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)
    st.divider()


def render_inputs() -> None:
    with st.form("analysis_form", clear_on_submit=False):
        st.text_area("Job Description", key="job_description", height=220)
        st.text_area("Resume (Optional)", key="resume_text", height=180)
        clicked = st.form_submit_button(
            "Analyze",
            type="primary",
            disabled=st.session_state.busy,
        )

    if clicked:
        job_description = (st.session_state.get("job_description") or "").strip()
        if len(job_description) < 20:
            st.warning("Please enter a more detailed job description.")
            return
        st.session_state.match_result = None
        st.session_state.tailor_result = None
        st.session_state.cover_letter_result = None
        st.session_state.busy = True
        st.session_state.trigger_run = True
        st.rerun()


def run_pipeline(config: UIConfig) -> None:
    if not st.session_state.trigger_run:
        return

    job_description = (st.session_state.get("job_description") or "").strip()
    if not job_description:
        st.session_state.busy = False
        st.session_state.trigger_run = False
        st.error("Job description is required.")
        return

    with st.spinner("Analyzing..."):
        match_result, error = call_backend(
            config,
            "/match",
            {"job_description": job_description},
        )
        if error:
            st.session_state.busy = False
            st.session_state.trigger_run = False
            st.error(error)
            return
        st.session_state.match_result = match_result

        tailor_result, error = call_backend(
            config,
            "/tailor",
            {"job_description": job_description},
        )
        if error:
            st.session_state.busy = False
            st.session_state.trigger_run = False
            st.warning(f"Tailoring unavailable: {error}")
            return
        st.session_state.tailor_result = tailor_result

        cover_letter_result, error = call_backend(
            config,
            "/cover-letter",
            {"job_description": job_description},
        )
        if error:
            st.session_state.busy = False
            st.session_state.trigger_run = False
            st.warning(f"Cover letter unavailable: {error}")
            return
        st.session_state.cover_letter_result = cover_letter_result

    st.session_state.busy = False
    st.session_state.trigger_run = False
    st.success("Analysis complete.")


def render_results() -> None:
    match_result = st.session_state.match_result
    tailor_result = st.session_state.tailor_result
    cover_letter_result = st.session_state.cover_letter_result

    if not match_result and not tailor_result and not cover_letter_result:
        return

    tabs = st.tabs(["Match", "Tailored Resume", "Cover Letter"])

    with tabs[0]:
        if not match_result:
            st.info("No match result yet.")
        else:
            st.metric("Match Score", match_result.get("score", "N/A"))
            st.write("Matched Skills")
            st.write(match_result.get("matched_skills", []))
            st.write("Missing Skills")
            st.write(match_result.get("missing_skills", []))

    with tabs[1]:
        if not tailor_result:
            st.info("No tailored resume yet.")
        else:
            payload = tailor_result.get("tailored_resume", {})
            st.subheader("Summary")
            st.write(payload.get("summary", ""))
            st.subheader("Experience")
            for line in payload.get("experience", []):
                st.write(line)
            st.subheader("Skills")
            st.write(payload.get("skills", []))

    with tabs[2]:
        if not cover_letter_result:
            st.info("No cover letter yet.")
        else:
            text = cover_letter_result.get("cover_letter", "")
            st.code(text, language="text")
            st.download_button(
                label="Download Cover Letter",
                data=text,
                file_name="cover_letter.txt",
                mime="text/plain",
            )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="centered")
    initialize_state()
    render_header()

    try:
        config = load_ui_config()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    st.caption(f"Backend: {config.backend_url}")
    render_inputs()
    run_pipeline(config)
    render_results()


if __name__ == "__main__":
    main()
