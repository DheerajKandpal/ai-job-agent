# Bugfix Requirements Document

## Introduction

The `match_resume_to_job` function in `app/services/matcher/matcher.py` incorrectly splits the job description into individual words before matching. This causes multi-word skills (e.g., "Power BI", "Machine Learning") to never match, even when they appear verbatim in the job description. The fix replaces word-set lookup with substring search against the full (lowercased) job description string.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a resume skill contains more than one word (e.g., "Power BI") THEN the system splits the job description into single words and fails to find the skill, incorrectly marking it as missing.

1.2 WHEN the job description contains the phrase "Power BI" THEN the system returns a match_score that does not count "Power BI" as matched, producing a lower score than expected.

### Expected Behavior (Correct)

2.1 WHEN a resume skill contains more than one word (e.g., "Power BI") THEN the system SHALL check whether the full skill string exists as a substring in the lowercased job description and count it as matched if found.

2.2 WHEN the job description contains the phrase "Power BI" and the resume lists "Power BI" as a skill THEN the system SHALL include "power bi" in `matched_skills` and reflect it in the match_score.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN all resume skills are single words (e.g., "Python", "SQL") THEN the system SHALL CONTINUE TO match them correctly against the job description and compute the same match_score as before.

3.2 WHEN a skill does not appear anywhere in the job description THEN the system SHALL CONTINUE TO list it in `missing_skills` and exclude it from the match_score.

3.3 WHEN the resume has no skills THEN the system SHALL CONTINUE TO return a match_score of 0 with empty matched and missing lists.

3.4 WHEN the function returns a result THEN the system SHALL CONTINUE TO return the same output format: `{"match_score": float, "matched_skills": list, "missing_skills": list}`.

---

## Bug Condition (Pseudocode)

```pascal
FUNCTION isBugCondition(skill)
  INPUT: skill of type string
  OUTPUT: boolean

  // Returns true when the skill contains a space (multi-word)
  RETURN " " IN skill
END FUNCTION
```

```pascal
// Property: Fix Checking
FOR ALL skill WHERE isBugCondition(skill) DO
  result ← match_resume_to_job'({skills: [skill]}, jd_containing_skill)
  ASSERT skill.lower() IN result.matched_skills
END FOR
```

```pascal
// Property: Preservation Checking
FOR ALL skill WHERE NOT isBugCondition(skill) DO
  ASSERT match_resume_to_job(resume, jd) = match_resume_to_job'(resume, jd)
END FOR
```
