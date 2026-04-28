# Requirements Document

## Introduction

The resume-to-job matcher needs a two-step scoring model. First, `extract_skills_from_jd` identifies which skills from the resume are explicitly mentioned in the job description — these become the JD-required skills and the denominator. Second, `match_resume_to_job` computes the score as matched skills divided by JD-required skills. This means a candidate who covers 3 of 4 JD-required skills scores 0.75, regardless of how many other skills they list.

## Glossary

- **Matcher**: The `match_resume_to_job` function in `app/services/matcher/matcher.py`.
- **Resume_Skills**: The list of skills extracted from the candidate's resume JSON (`resume_json["skills"]`), normalised to lowercase.
- **Job_Description**: The raw text string describing the open position.
- **JD_Required_Skills**: The output of `extract_skills_from_jd` — the subset of `known_skills` whose lowercase form appears as a substring in the lowercased Job_Description.
- **Matched_Skills**: The intersection of Resume_Skills and JD_Required_Skills.
- **Missing_Skills**: JD_Required_Skills that are NOT present in Resume_Skills.
- **Match_Score**: `len(Matched_Skills) / len(JD_Required_Skills)` when JD_Required_Skills is non-empty, otherwise `0.0`.

## Requirements

### Requirement 1: JD Skill Extraction

**User Story:** As a recruiter, I want the system to identify which skills from a candidate's resume are explicitly required by the job description, so that scoring is based on what the JD actually asks for.

#### Acceptance Criteria

1. THE Matcher SHALL expose a function `extract_skills_from_jd(job_description: str, known_skills: list) -> list`.
2. WHEN called, `extract_skills_from_jd` SHALL normalise `job_description` to lowercase before any comparison.
3. FOR each skill in `known_skills`, `extract_skills_from_jd` SHALL check whether the lowercased skill appears as a substring in the lowercased `job_description`.
4. `extract_skills_from_jd` SHALL return a list containing only the skills (lowercased) that were found in the job description.
5. `extract_skills_from_jd` SHALL preserve multi-word skill matching by using substring search on the full string, NOT by splitting the JD into tokens.

### Requirement 2: Job-Relevant Denominator Scoring

**User Story:** As a recruiter, I want the match score to reflect how well a candidate covers the skills I asked for, so that candidates with broad skill sets are not unfairly penalised.

#### Acceptance Criteria

1. WHEN `match_resume_to_job` is called, THE Matcher SHALL call `extract_skills_from_jd(job_description, resume_skills)` to obtain `jd_required_skills`.
2. THE Matcher SHALL compute `match_score` as `len(matched_skills) / len(jd_required_skills)` where `matched_skills` is the intersection of Resume_Skills and JD_Required_Skills.
3. WHEN the JD mentions 4 resume skills and the candidate has 3 of them, THE Matcher SHALL return `match_score` of `0.75`.
4. WHEN the JD mentions 3 resume skills and the candidate has all 3, THE Matcher SHALL return `match_score` of `1.0`.
5. THE Matcher SHALL return `matched_skills` as the list of skills present in both the resume and the JD.
6. THE Matcher SHALL return `missing_skills` as the list of JD_Required_Skills not present in Resume_Skills.

### Requirement 3: Edge Case — No Job-Relevant Skills

**User Story:** As a recruiter, I want the system to handle resumes with no matching skills gracefully, so that the application does not crash or return invalid scores.

#### Acceptance Criteria

1. IF `jd_required_skills` is empty, THEN THE Matcher SHALL return `match_score` of `0.0`.
2. IF `jd_required_skills` is empty, THEN THE Matcher SHALL return `matched_skills` as an empty list.
3. IF `jd_required_skills` is empty, THEN THE Matcher SHALL return `missing_skills` as an empty list.
4. IF `resume_json` contains no `skills` key or an empty skills list, THEN THE Matcher SHALL return `match_score` of `0.0` and empty lists for both `matched_skills` and `missing_skills`.

### Requirement 3: Output Contract

**User Story:** As a developer integrating the Matcher, I want the output format to remain unchanged, so that downstream consumers require no modification.

#### Acceptance Criteria

1. THE Matcher SHALL return a dictionary with exactly the keys `match_score`, `matched_skills`, and `missing_skills`.
2. THE Matcher SHALL return `match_score` as a float rounded to two decimal places.
3. THE Matcher SHALL return `matched_skills` as a list of strings.
4. THE Matcher SHALL return `missing_skills` as a list of strings.

### Requirement 4: No External NLP Libraries

**User Story:** As a maintainer, I want the matching logic to use only Python built-ins, so that the service has no heavy NLP dependencies.

#### Acceptance Criteria

1. THE Matcher SHALL implement all skill-matching logic using Python standard library string operations only.
2. THE Matcher SHALL NOT import or invoke any third-party NLP library (e.g., spaCy, NLTK, transformers).
