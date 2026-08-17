from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_BRACKET = re.compile(r"【([^】]+)】|\[([^\]]+)\]")
_IGNORED_TAG_PART = re.compile(
    r"^(?:v?\d+(?:\.\d+)*|trunk|主干|review|xf)$", re.IGNORECASE
)
_PRODUCT_VERSION_TAG = re.compile(r"^.+\d+\.\d+$", re.IGNORECASE)
_NOISE = re.compile(r"(?i)\b(?:bug|defect|issue|v?\d+(?:\.\d+)+|trunk|review|xf)\b")
_NON_WORD = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")
_FEATURE_SPLIT = re.compile(r"[-—–/／:：]")
_EXCLUDED_FAILURES = {"scope_discovery_failed", "source_mismatch"}


@dataclass(frozen=True)
class SimilarLocalizationReport:
    task_id: str
    run_id: str
    external_ticket_id: str
    title: str
    path: Path
    score: float
    matched_feature: str | None


@dataclass(frozen=True)
class _TitleFeatures:
    normalized: str
    feature: str | None
    feature_tag: str | None
    bigrams: frozenset[str]


def _compact(value: str) -> str:
    return _NON_WORD.sub("", value).casefold()


def _is_ignored_tag(value: str) -> bool:
    if _PRODUCT_VERSION_TAG.fullmatch(value.strip()):
        return True
    parts = [item.strip() for item in re.split(r"[、,/+，\s]+", value) if item.strip()]
    return bool(parts) and all(_IGNORED_TAG_PART.fullmatch(item) for item in parts)


def _title_features(title: str) -> _TitleFeatures:
    semantic_tags: list[str] = []
    for match in _BRACKET.finditer(title):
        raw = str(match.group(1) or match.group(2) or "").strip()
        compact = _compact(raw)
        if compact and not _is_ignored_tag(raw):
            semantic_tags.append(raw)
    body = _BRACKET.sub("", title)
    normalized = _compact(_NOISE.sub("", body))
    source = semantic_tags[-1] if semantic_tags else ""
    feature_parts = [_compact(item) for item in _FEATURE_SPLIT.split(source) if _compact(item)]
    feature = feature_parts[0] if feature_parts else None
    feature_tag = _compact(source) or None
    bigram_source = _compact("".join(semantic_tags) + body)
    bigrams = frozenset(
        bigram_source[index : index + 2]
        for index in range(max(0, len(bigram_source) - 1))
    )
    return _TitleFeatures(normalized, feature, feature_tag, bigrams)


def title_similarity(left: str, right: str) -> tuple[float, str | None]:
    a = _title_features(left)
    b = _title_features(right)
    overlap = len(a.bigrams & b.bigrams)
    dice = 0.0 if not a.bigrams or not b.bigrams else 2 * overlap / (len(a.bigrams) + len(b.bigrams))
    if a.feature and a.feature == b.feature:
        score = 0.70 + (0.20 if a.feature_tag == b.feature_tag else 0.0) + 0.10 * dice
        return min(score, 1.0), a.feature
    return dice, None


class SimilarReportFinder:
    def __init__(self, connection: sqlite3.Connection, data_root: Path) -> None:
        self.connection = connection
        self.data_root = data_root.resolve()

    def find(
        self,
        *,
        current_run_id: str,
        current_task_id: str,
        project_id: str,
        title: str,
        localization_source_id: str,
        localization_workspace: Path,
        minimum_score: float = 0.62,
    ) -> SimilarLocalizationReport | None:
        rows = self.connection.execute(
            """SELECT report.task_run_id AS run_id,
                      report.relative_path AS report_path,
                      report.sha256 AS report_sha256,
                      source.relative_path AS source_path,
                      t.id AS task_id,
                      t.current_run_id,
                      t.failure_json,
                      tr.external_ticket_id,
                      COALESCE(snapshot.title,tr.title) AS title,
                      COALESCE(r.finished_at,r.started_at,r.created_at) AS recency
                 FROM artifacts report
                 JOIN task_runs r ON r.id=report.task_run_id
                 JOIN tasks t ON t.id=r.task_id
                 JOIN ticket_records tr ON tr.id=t.ticket_record_id
                 LEFT JOIN ticket_snapshots snapshot ON snapshot.id=r.ticket_snapshot_id
                 JOIN artifacts source ON source.task_run_id=r.id
                                      AND source.stage_id='prepare'
                                      AND source.artifact_type='source_manifest'
                WHERE report.artifact_type='localization_report'
                  AND report.stage_id='discovery'
                  AND report.task_run_id<>?
                  AND t.id<>?
                  AND t.project_id=?
                  AND EXISTS(
                      SELECT 1 FROM stage_runs stage
                       WHERE stage.task_run_id=r.id
                         AND stage.stage_id='discovery'
                         AND stage.status='completed'
                  )
                ORDER BY recency DESC
                LIMIT 100""",
            (current_run_id, current_task_id, project_id),
        ).fetchall()
        expected_workspace = os.path.normcase(str(localization_workspace.resolve()))
        matches: list[tuple[float, str, SimilarLocalizationReport]] = []
        for row in rows:
            if self._has_excluded_failure(row):
                continue
            source_path = self._safe_path(str(row["source_path"]))
            report_path = self._safe_path(str(row["report_path"]))
            if source_path is None or report_path is None or not report_path.is_file():
                continue
            try:
                source = json.loads(source_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if str(source.get("id") or "") != localization_source_id:
                continue
            source_workspace = os.path.normcase(str(Path(str(source.get("workspace") or "")).resolve()))
            if source_workspace != expected_workspace:
                continue
            try:
                report_bytes = report_path.read_bytes()
            except OSError:
                continue
            if not report_bytes.strip() or hashlib.sha256(report_bytes).hexdigest() != str(row["report_sha256"]):
                continue
            score, feature = title_similarity(title, str(row["title"]))
            if score < minimum_score:
                continue
            report = SimilarLocalizationReport(
                task_id=str(row["task_id"]),
                run_id=str(row["run_id"]),
                external_ticket_id=str(row["external_ticket_id"]),
                title=str(row["title"]),
                path=report_path,
                score=score,
                matched_feature=feature,
            )
            matches.append((score, str(row["recency"]), report))
        return max(matches, key=lambda item: (item[0], item[1]))[2] if matches else None

    def _safe_path(self, relative: str) -> Path | None:
        path = (self.data_root / relative).resolve()
        try:
            path.relative_to(self.data_root)
        except ValueError:
            return None
        return path

    @staticmethod
    def _has_excluded_failure(row: sqlite3.Row) -> bool:
        if str(row["current_run_id"] or "") != str(row["run_id"]):
            return False
        try:
            failure = json.loads(str(row["failure_json"] or "null"))
        except json.JSONDecodeError:
            return False
        return isinstance(failure, dict) and str(failure.get("code") or "") in _EXCLUDED_FAILURES
