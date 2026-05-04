"""
Preservation property tests — Task 2.

These tests encode behaviors that MUST NOT change after the fix is applied.
They are written against UNFIXED code and MUST PASS on unfixed code.

Behaviors under test (non-buggy paths — none of the three bug conditions hold):
  P1 — Empty / whitespace-only job_description raises ValueError in process_match
  P2 — Empty / whitespace-only job_description raises ValueError in process_tailor
  P3 — Resume not found in DB raises ValueError("resume not found") in process_match
  P4 — Resume not found in DB raises ValueError("resume not found") in process_tailor
  P5 — generate_tailored_resume returns a valid dict with keys summary/experience/skills
       when subprocess.run returns well-formed JSON with returncode=0
  P6 — match_resume_to_job: when resume has no skills, match_score=0.0 and matched_skills=[]
  P7 — process_match always returns a dict with keys match_score (float) and matched_skills (list)

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8
"""

import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed_process(returncode: int, stdout: str, stderr: str = "") -> MagicMock:
    mock_proc = MagicMock()
    mock_proc.returncode = returncode
    mock_proc.stdout = stdout
    mock_proc.stderr = stderr
    return mock_proc


# ---------------------------------------------------------------------------
# P1 / P2 — Empty / whitespace-only job_description raises ValueError
# ---------------------------------------------------------------------------

class TestEmptyJobDescriptionRaisesValueError(unittest.TestCase):
    """
    Preservation: empty or whitespace-only job_description must continue to
    raise ValueError in both process_match and process_tailor.

    These paths do NOT involve the three bug conditions — they are pure
    input-validation paths that the fix must not touch.

    Validates: Requirements 3.3, 3.4
    """

    # --- process_match ---

    def test_process_match_empty_string_raises(self):
        from app.services.match_service import process_match
        with self.assertRaises(ValueError):
            process_match("")

    def test_process_match_whitespace_only_raises(self):
        from app.services.match_service import process_match
        with self.assertRaises(ValueError):
            process_match("   ")

    def test_process_match_tab_only_raises(self):
        from app.services.match_service import process_match
        with self.assertRaises(ValueError):
            process_match("\t\n  ")

    # --- process_tailor ---

    def test_process_tailor_empty_string_raises(self):
        from app.services.tailor_service import process_tailor
        with self.assertRaises(ValueError):
            process_tailor("")

    def test_process_tailor_whitespace_only_raises(self):
        from app.services.tailor_service import process_tailor
        with self.assertRaises(ValueError):
            process_tailor("   ")

    def test_process_tailor_tab_only_raises(self):
        from app.services.tailor_service import process_tailor
        with self.assertRaises(ValueError):
            process_tailor("\t\n  ")


# ---------------------------------------------------------------------------
# P1 / P2 — Property-based: any whitespace-only string raises ValueError
# ---------------------------------------------------------------------------

class TestEmptyJobDescriptionPropertyBased(unittest.TestCase):
    """
    Property-based version of the empty-JD validation tests.

    For any string composed entirely of whitespace characters,
    both process_match and process_tailor must raise ValueError.

    Validates: Requirements 3.3, 3.4
    """

    @given(st.text(alphabet=st.characters(whitelist_categories=("Zs", "Cc")), min_size=0))
    @h_settings(max_examples=10)
    def test_process_match_whitespace_string_raises(self, whitespace_jd: str):
        """
        **Validates: Requirements 3.3**
        For any whitespace-only (or empty) job_description string,
        process_match must raise ValueError.
        """
        from app.services.match_service import process_match
        with self.assertRaises(ValueError):
            process_match(whitespace_jd)

    @given(st.text(alphabet=st.characters(whitelist_categories=("Zs", "Cc")), min_size=0))
    @h_settings(max_examples=10)
    def test_process_tailor_whitespace_string_raises(self, whitespace_jd: str):
        """
        **Validates: Requirements 3.4**
        For any whitespace-only (or empty) job_description string,
        process_tailor must raise ValueError.
        """
        from app.services.tailor_service import process_tailor
        with self.assertRaises(ValueError):
            process_tailor(whitespace_jd)


# ---------------------------------------------------------------------------
# P3 / P4 — Resume not found raises ValueError("resume not found")
# ---------------------------------------------------------------------------

class TestResumeNotFoundRaisesValueError(unittest.TestCase):
    """
    Preservation: when the DB returns None for the resume, both process_match
    and process_tailor must raise ValueError("resume not found").

    Validates: Requirements 3.5
    """

    def test_process_match_resume_not_found_raises(self):
        """
        When get_resume returns None (resume absent from DB),
        process_match must raise ValueError with message "resume not found".
        """
        from app.services.match_service import process_match

        with patch("app.services.match_service.cache_get", return_value=None), \
             patch("app.services.match_service.get_resume", return_value=None), \
             patch("app.services.match_service.cache_set"):
            with self.assertRaises(ValueError) as ctx:
                process_match("Python developer needed.")
        self.assertIn("resume not found", str(ctx.exception))

    def test_process_tailor_resume_not_found_raises(self):
        """
        When get_resume returns None (resume absent from DB),
        process_tailor must raise ValueError with message "resume not found".
        """
        from app.services.tailor_service import process_tailor

        with patch("app.services.tailor_service.cache_get", return_value=None), \
             patch("app.services.tailor_service.get_resume", return_value=None), \
             patch("app.services.tailor_service.cache_set"):
            with self.assertRaises(ValueError) as ctx:
                process_tailor("Python developer needed.")
        self.assertIn("resume not found", str(ctx.exception))

    def test_process_match_resume_not_found_message_exact(self):
        """
        The ValueError message must be exactly "resume not found".
        """
        from app.services.match_service import process_match

        with patch("app.services.match_service.cache_get", return_value=None), \
             patch("app.services.match_service.get_resume", return_value=None), \
             patch("app.services.match_service.cache_set"):
            with self.assertRaises(ValueError) as ctx:
                process_match("Some job description.")
        self.assertEqual(str(ctx.exception), "resume not found")

    def test_process_tailor_resume_not_found_message_exact(self):
        """
        The ValueError message must be exactly "resume not found".
        """
        from app.services.tailor_service import process_tailor

        with patch("app.services.tailor_service.cache_get", return_value=None), \
             patch("app.services.tailor_service.get_resume", return_value=None), \
             patch("app.services.tailor_service.cache_set"):
            with self.assertRaises(ValueError) as ctx:
                process_tailor("Some job description.")
        self.assertEqual(str(ctx.exception), "resume not found")


# ---------------------------------------------------------------------------
# P5 — generate_tailored_resume returns valid dict on successful LLM response
# ---------------------------------------------------------------------------

class TestGenerateTailoredResumeSuccessPath(unittest.TestCase):
    """
    Preservation: when subprocess.run returns well-formed JSON with returncode=0,
    generate_tailored_resume must return a dict with keys summary, experience, skills.

    This is the non-buggy success path — the fix must not break it.

    Validates: Requirements 3.8 (successful LLM path preservation)
    """

    def _run_with_json_response(self, payload: dict) -> dict:
        """Helper: patch subprocess.run to return valid JSON, call generate_tailored_resume."""
        from app.services.llm.ollama_client import generate_tailored_resume

        resume = {"skills": ["Python"], "summary": "Analyst", "experience": []}
        jd = "Python developer needed."
        stdout_text = json.dumps(payload)

        with patch(
            "app.services.llm.ollama_client.subprocess.run",
            return_value=_make_completed_process(returncode=0, stdout=stdout_text),
        ):
            return generate_tailored_resume(resume, jd)

    def test_returns_dict_with_required_keys(self):
        """
        A well-formed JSON response must produce a dict with summary, experience, skills.
        """
        payload = {"summary": "Tailored summary", "experience": ["Led team"], "skills": ["Python"]}
        result = self._run_with_json_response(payload)

        self.assertIsInstance(result, dict)
        self.assertIn("summary", result)
        self.assertIn("experience", result)
        self.assertIn("skills", result)

    def test_summary_is_string(self):
        payload = {"summary": "Data analyst", "experience": [], "skills": []}
        result = self._run_with_json_response(payload)
        self.assertIsInstance(result["summary"], str)

    def test_experience_is_list(self):
        payload = {"summary": "", "experience": ["Built dashboards"], "skills": []}
        result = self._run_with_json_response(payload)
        self.assertIsInstance(result["experience"], list)

    def test_skills_is_list(self):
        payload = {"summary": "", "experience": [], "skills": ["Python", "SQL"]}
        result = self._run_with_json_response(payload)
        self.assertIsInstance(result["skills"], list)

    def test_does_not_raise_on_success(self):
        """
        The success path must never raise — not RuntimeError, not anything.
        """
        payload = {"summary": "ok", "experience": ["item"], "skills": ["Python"]}
        try:
            result = self._run_with_json_response(payload)
        except Exception as exc:
            self.fail(
                f"generate_tailored_resume raised unexpectedly on success path: {exc}"
            )

    def test_empty_valid_json_returns_sanitized_dict(self):
        """
        Even an empty-values JSON response (the LLM fallback shape) must return
        a dict with the three required keys.
        """
        payload = {"summary": "", "experience": [], "skills": []}
        result = self._run_with_json_response(payload)

        self.assertIsInstance(result, dict)
        self.assertIn("summary", result)
        self.assertIn("experience", result)
        self.assertIn("skills", result)


# ---------------------------------------------------------------------------
# P5 — Property-based: any well-formed JSON response produces valid dict
# ---------------------------------------------------------------------------

# Strategy: generate arbitrary summary strings, experience lists, skills lists
_summary_st = st.text(min_size=0, max_size=200)
_str_list_st = st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10)

_valid_llm_response_st = st.fixed_dictionaries({
    "summary": _summary_st,
    "experience": _str_list_st,
    "skills": _str_list_st,
})


class TestGenerateTailoredResumePropertyBased(unittest.TestCase):
    """
    Property-based preservation tests for the successful LLM path.

    Validates: Requirements 3.8
    """

    @given(_valid_llm_response_st)
    @h_settings(max_examples=50)
    def test_valid_llm_response_always_returns_dict_with_required_keys(self, payload: dict):
        """
        **Validates: Requirements 3.8**
        For any well-formed JSON response from the LLM (dict with summary,
        experience, skills), generate_tailored_resume must return a dict
        containing exactly those three keys and must not raise.
        """
        from app.services.llm.ollama_client import generate_tailored_resume

        resume = {"skills": ["Python"], "summary": "Analyst", "experience": []}
        jd = "Python developer needed."
        stdout_text = json.dumps(payload)

        with patch(
            "app.services.llm.ollama_client.subprocess.run",
            return_value=_make_completed_process(returncode=0, stdout=stdout_text),
        ):
            result = generate_tailored_resume(resume, jd)

        self.assertIsInstance(result, dict, "Result must be a dict")
        self.assertIn("summary", result, "Result must have 'summary' key")
        self.assertIn("experience", result, "Result must have 'experience' key")
        self.assertIn("skills", result, "Result must have 'skills' key")
        self.assertIsInstance(result["summary"], str, "'summary' must be a str")
        self.assertIsInstance(result["experience"], list, "'experience' must be a list")
        self.assertIsInstance(result["skills"], list, "'skills' must be a list")


# ---------------------------------------------------------------------------
# P6 — match_resume_to_job: no skills → match_score=0.0, matched_skills=[]
# ---------------------------------------------------------------------------

class TestMatchResumeToJobNoSkills(unittest.TestCase):
    """
    Preservation: when the resume has no skills, match_resume_to_job must
    return match_score=0.0 and matched_skills=[].

    This tests the internal scoring logic of matcher.py directly — the fix
    does not touch this file, so this behavior must be identical before and
    after the fix.

    Validates: Requirements 3.8 (match_resume_to_job internal logic unchanged)
    """

    def test_no_skills_returns_zero_score(self):
        from app.services.matcher.matcher import match_resume_to_job

        resume = {"skills": [], "summary": "Analyst", "experience": []}
        result = match_resume_to_job(resume, "Python developer needed.")

        self.assertEqual(result["match_score"], 0.0)

    def test_no_skills_returns_empty_matched_skills(self):
        from app.services.matcher.matcher import match_resume_to_job

        resume = {"skills": [], "summary": "Analyst", "experience": []}
        result = match_resume_to_job(resume, "Python developer needed.")

        self.assertEqual(result["matched_skills"], [])

    def test_missing_skills_key_returns_zero_score(self):
        """Resume dict with no 'skills' key at all behaves the same as empty skills."""
        from app.services.matcher.matcher import match_resume_to_job

        resume = {"summary": "Analyst", "experience": []}
        result = match_resume_to_job(resume, "Python developer needed.")

        self.assertEqual(result["match_score"], 0.0)
        self.assertEqual(result["matched_skills"], [])


# ---------------------------------------------------------------------------
# P6 — Property-based: no skills always yields 0.0 / []
# ---------------------------------------------------------------------------

class TestMatchResumeToJobNoSkillsPropertyBased(unittest.TestCase):
    """
    Property-based version of the no-skills scoring test.

    Validates: Requirements 3.8
    """

    @given(st.text(min_size=1, max_size=500))
    @h_settings(max_examples=100)
    def test_no_skills_always_zero_score_for_any_jd(self, jd: str):
        """
        **Validates: Requirements 3.8**
        For any job description string, a resume with no skills must always
        produce match_score=0.0 and matched_skills=[].
        """
        from app.services.matcher.matcher import match_resume_to_job

        resume = {"skills": [], "summary": "Analyst", "experience": []}
        result = match_resume_to_job(resume, jd)

        self.assertEqual(
            result["match_score"],
            0.0,
            msg=f"Expected match_score=0.0 for empty skills, got {result['match_score']} (jd={jd!r})",
        )
        self.assertEqual(
            result["matched_skills"],
            [],
            msg=f"Expected matched_skills=[] for empty skills, got {result['matched_skills']} (jd={jd!r})",
        )


# ---------------------------------------------------------------------------
# P7 — process_match structural guarantee: always returns match_score + matched_skills
# ---------------------------------------------------------------------------

class TestProcessMatchStructuralGuarantee(unittest.TestCase):
    """
    Preservation: process_match must always return a dict with keys
    match_score (float) and matched_skills (list) when a resume is present
    and job_description is non-empty.

    This structural guarantee holds on both unfixed and fixed code.

    Validates: Requirements 3.8
    """

    def _call_process_match(self, resume: dict, jd: str) -> dict:
        """Helper: patch DB/cache and call process_match."""
        with patch("app.services.match_service.cache_get", return_value=None), \
             patch("app.services.match_service.get_resume", return_value=resume), \
             patch("app.services.match_service.cache_set"):
            from app.services.match_service import process_match
            return process_match(jd)

    def test_returns_dict(self):
        resume = {"skills": ["Python"], "summary": "Analyst", "experience": []}
        result = self._call_process_match(resume, "Python developer needed.")
        self.assertIsInstance(result, dict)

    def test_has_match_score_key(self):
        resume = {"skills": ["Python"], "summary": "Analyst", "experience": []}
        result = self._call_process_match(resume, "Python developer needed.")
        self.assertIn("match_score", result)

    def test_has_matched_skills_key(self):
        resume = {"skills": ["Python"], "summary": "Analyst", "experience": []}
        result = self._call_process_match(resume, "Python developer needed.")
        self.assertIn("matched_skills", result)

    def test_match_score_is_float(self):
        resume = {"skills": ["Python"], "summary": "Analyst", "experience": []}
        result = self._call_process_match(resume, "Python developer needed.")
        self.assertIsInstance(result["match_score"], float)

    def test_matched_skills_is_list(self):
        resume = {"skills": ["Python"], "summary": "Analyst", "experience": []}
        result = self._call_process_match(resume, "Python developer needed.")
        self.assertIsInstance(result["matched_skills"], list)

    def test_no_skills_resume_returns_zero_score(self):
        """
        Structural guarantee holds even when resume has no skills.
        match_score must be 0.0 (float) and matched_skills must be [].
        """
        resume = {"skills": [], "summary": "Analyst", "experience": []}
        result = self._call_process_match(resume, "Python developer needed.")
        self.assertEqual(result["match_score"], 0.0)
        self.assertEqual(result["matched_skills"], [])


# ---------------------------------------------------------------------------
# P7 — Property-based: structural guarantee across arbitrary inputs
# ---------------------------------------------------------------------------

# Strategy: generate resume dicts with arbitrary skill lists
_skill_st = st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Zs")))
_resume_st = st.fixed_dictionaries({
    "skills": st.lists(_skill_st, min_size=0, max_size=20),
    "summary": st.text(min_size=0, max_size=200),
    "experience": st.lists(st.text(min_size=0, max_size=100), min_size=0, max_size=5),
})
_nonempty_jd_st = st.text(min_size=1, max_size=500).filter(lambda s: s.strip())


class TestProcessMatchStructuralPropertyBased(unittest.TestCase):
    """
    Property-based structural guarantee for process_match.

    Validates: Requirements 3.8
    """

    @given(_resume_st, _nonempty_jd_st)
    @h_settings(max_examples=100)
    def test_process_match_always_returns_correct_structure(self, resume: dict, jd: str):
        """
        **Validates: Requirements 3.8**
        For any resume dict and any non-empty job_description string,
        process_match must return a dict with:
          - 'match_score' key whose value is a float
          - 'matched_skills' key whose value is a list
        """
        with patch("app.services.match_service.cache_get", return_value=None), \
             patch("app.services.match_service.get_resume", return_value=resume), \
             patch("app.services.match_service.cache_set"):
            from app.services.match_service import process_match
            result = process_match(jd)

        self.assertIsInstance(result, dict, "process_match must return a dict")
        self.assertIn("match_score", result, "Result must have 'match_score' key")
        self.assertIn("matched_skills", result, "Result must have 'matched_skills' key")
        self.assertIsInstance(result["match_score"], float, "'match_score' must be a float")
        self.assertIsInstance(result["matched_skills"], list, "'matched_skills' must be a list")


if __name__ == "__main__":
    unittest.main(verbosity=2)
