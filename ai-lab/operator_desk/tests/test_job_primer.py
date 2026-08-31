from __future__ import annotations

from operator_desk.errors import JOB_NOT_FOUND
from operator_desk.job_primer import load_job_manifest, load_job_primer


def test_manifest_has_four_jobs():
    m = load_job_manifest()
    assert set(m) >= {"company_email", "growflow_retail", "machine_actions", "repo_awareness"}


def test_load_job_primer(jobs_dir):
    bundle = load_job_primer("growflow_retail")
    assert bundle.ok is True
    assert "Never refresh" in bundle.primer_markdown
    assert bundle.job_id == "growflow_retail"


def test_missing_job():
    bundle = load_job_primer("no_such_job")
    assert bundle.ok is False
    assert bundle.error_code == JOB_NOT_FOUND
