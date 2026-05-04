"""
Bug condition exploration tests.

These tests MUST FAIL on unfixed code — that is the expected outcome.
Failure confirms the bugs exist. Do NOT fix the code or the tests when they fail.

Bugs under test:
  Bug 1 — Swapped arguments in match_service.process_match
  Bug 2 — Swapped arguments in tailor_service.process_tailor
  Bug 3a/b/c — Silent LLM failure in ollama_client.generate_tailored_resume
"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Bug 1 — Match argument order
# ---------------------------------------------------------------------------

class TestBug1MatchArgumentOrder(unittest.TestCase):
    """
    process_match calls match(job_description, resume) instead of
    match(resume, job_description).  Because match_resume_to_job calls
    .get("skills", []) on its first argument, passing a string there
    silently returns match_score=0.0 and matched_skills=[].

    Expected (correct) behaviour: when the resume has skills that appear in
    the JD, match_score > 0.0 and matched_skills is non-empty.

    On UNFIXED code this assertion FAILS — that is the expected outcome.
    """

    def test_match_score_nonzero_when_skills_overlap(self):
        """
        Bug 1 counterexample:
          resume skills = ["Python", "SQL"], JD mentions "Python"
          → unfixed code returns match_score=0.0, matched_skills=[]
          → fixed code should return match_score > 0.0, matched_skills non-empty
        """
        resume_dict = {
            "skills": ["Python", "SQL"],
            "summary": "Data analyst",
            "experience": [],
        }
        jd_string = "Looking for a Python developer with SQL experience."

        with patch(
            "app.services.match_service.get_resume",
            return_value=resume_dict,
        ), patch(
            "app.services.match_service.cache_get",
            return_value=None,
        ), patch(
            "app.services.match_service.cache_set",
        ):
            from app.services.match_service import process_match

            result = process_match(jd_string)

        # On unfixed code: match_score=0.0, matched_skills=[]
        # These assertions FAIL on unfixed code — that confirms Bug 1 exists.
        self.assertGreater(
            result["match_score"],
            0.0,
            msg=(
                "BUG 1 DETECTED: match_score is 0.0 even though resume skills "
                "overlap the JD. job_description string is being passed as "
                "resume_json to match_resume_to_job."
            ),
        )
        self.assertTrue(
            len(result["matched_skills"]) > 0,
            msg=(
                "BUG 1 DETECTED: matched_skills is empty even though resume "
                "skills overlap the JD."
            ),
        )


# ---------------------------------------------------------------------------
# Bug 2 — Tailor argument order
# ---------------------------------------------------------------------------

class TestBug2TailorArgumentOrder(unittest.TestCase):
    """
    process_tailor calls generate_tailored_resume(job_description, resume)
    instead of generate_tailored_resume(resume, job_description).

    Expected (correct) behaviour: generate_tailored_resume is called with
    the resume dict as the first positional argument.

    On UNFIXED code the mock receives (jd_string, resume_dict) — the assertion
    FAILS, confirming Bug 2 exists.
    """

    def test_generate_tailored_resume_called_with_resume_first(self):
        """
        Bug 2 counterexample:
          mock receives call_args[0][0] = jd_string (a str) instead of resume_dict (a dict)
          → unfixed code: typeof(call_args[0]) = string AND typeof(call_args[1]) = dict
        """
        resume_dict = {
            "skills": ["Python", "SQL"],
            "summary": "Data analyst",
            "experience": [],
        }
        jd_string = "Looking for a Python developer."

        mock_generate = MagicMock(
            return_value={"summary": "tailored", "experience": [], "skills": ["Python"]}
        )

        with patch(
            "app.services.tailor_service.get_resume",
            return_value=resume_dict,
        ), patch(
            "app.services.tailor_service.cache_get",
            return_value=None,
        ), patch(
            "app.services.tailor_service.cache_set",
        ), patch(
            "app.services.tailor_service.generate_tailored_resume",
            mock_generate,
        ):
            from app.services.tailor_service import process_tailor

            process_tailor(jd_string)

        # Verify the mock was called exactly once
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args[0]  # positional args tuple

        # On unfixed code: call_args[0] is jd_string (str), call_args[1] is resume_dict (dict)
        # These assertions FAIL on unfixed code — that confirms Bug 2 exists.
        self.assertIsInstance(
            call_args[0],
            dict,
            msg=(
                f"BUG 2 DETECTED: generate_tailored_resume was called with "
                f"call_args[0]={type(call_args[0]).__name__!r} (expected dict). "
                f"job_description string is in the resume_json slot."
            ),
        )
        self.assertIsInstance(
            call_args[1],
            str,
            msg=(
                f"BUG 2 DETECTED: generate_tailored_resume was called with "
                f"call_args[1]={type(call_args[1]).__name__!r} (expected str). "
                f"resume dict is in the job_description slot."
            ),
        )


# ---------------------------------------------------------------------------
# Bug 3 — Silent LLM failure
# ---------------------------------------------------------------------------

class TestBug3LLMSilentFailure(unittest.TestCase):
    """
    generate_tailored_resume catches every failure path and returns
    sanitized_fallback silently instead of raising RuntimeError.

    Expected (correct) behaviour: RuntimeError is raised on all failure paths.

    On UNFIXED code these assertions FAIL — that confirms Bug 3 exists.
    """

    def _make_completed_process(self, returncode: int, stdout: str) -> MagicMock:
        mock_proc = MagicMock()
        mock_proc.returncode = returncode
        mock_proc.stdout = stdout
        mock_proc.stderr = ""
        return mock_proc

    def test_bug3a_timeout_raises_runtime_error(self):
        """
        Bug 3a counterexample:
          subprocess.run raises TimeoutExpired
          → unfixed code returns {"summary": "", "experience": [], "skills": []}
          → fixed code should raise RuntimeError
        """
        resume = {"skills": ["Python"], "summary": "", "experience": []}
        jd = "Python developer needed."

        with patch(
            "app.services.llm.ollama_client.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ollama", timeout=30),
        ):
            from app.services.llm.ollama_client import generate_tailored_resume

            with self.assertRaises(
                RuntimeError,
                msg=(
                    "BUG 3a DETECTED: generate_tailored_resume did not raise "
                    "RuntimeError on TimeoutExpired — it returned silently."
                ),
            ):
                generate_tailored_resume(resume, jd)

    def test_bug3b_nonzero_exit_code_raises_runtime_error(self):
        """
        Bug 3b counterexample:
          subprocess.run returns returncode=1, stdout=""
          → unfixed code returns empty fallback dict
          → fixed code should raise RuntimeError
        """
        resume = {"skills": ["Python"], "summary": "", "experience": []}
        jd = "Python developer needed."

        with patch(
            "app.services.llm.ollama_client.subprocess.run",
            return_value=self._make_completed_process(returncode=1, stdout=""),
        ):
            from app.services.llm.ollama_client import generate_tailored_resume

            with self.assertRaises(
                RuntimeError,
                msg=(
                    "BUG 3b DETECTED: generate_tailored_resume did not raise "
                    "RuntimeError when subprocess returned exit code 1."
                ),
            ):
                generate_tailored_resume(resume, jd)

    def test_bug3c_empty_stdout_raises_runtime_error(self):
        """
        Bug 3c counterexample:
          subprocess.run returns returncode=0, stdout=""
          → unfixed code returns empty fallback dict
          → fixed code should raise RuntimeError
        """
        resume = {"skills": ["Python"], "summary": "", "experience": []}
        jd = "Python developer needed."

        with patch(
            "app.services.llm.ollama_client.subprocess.run",
            return_value=self._make_completed_process(returncode=0, stdout=""),
        ):
            from app.services.llm.ollama_client import generate_tailored_resume

            with self.assertRaises(
                RuntimeError,
                msg=(
                    "BUG 3c DETECTED: generate_tailored_resume did not raise "
                    "RuntimeError when subprocess returned empty stdout."
                ),
            ):
                generate_tailored_resume(resume, jd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
