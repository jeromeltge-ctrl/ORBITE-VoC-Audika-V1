import sys
import os
import json
import sqlite3
import csv
import traceback

from pathlib import Path


# =====================================================
# 1. ENCODAGE UTF-8 ELECTRON / PYTHON
# =====================================================

for stream in (sys.stdin, sys.stdout, sys.stderr):
    try:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(
                encoding="utf-8",
                errors="strict"
            )
    except (AttributeError, OSError, ValueError):
        pass


# =====================================================
# 2. CONFIGURATION DES DONNEES
# =====================================================

os.environ.setdefault(
    "ORBITE_DATA_DIR",
    str(Path.home() / ".orbite-voc")
)


# =====================================================
# 3. MODULES ORBITE
# =====================================================

import orbite_data as d
import survey_library as lib

import nps_analytics as npsa
import question_analytics as qa
import orb_q06_bridge as q06
import network_analytics as net

import ereputation_bridge as er
import shared_reference
import google_view

import import_deletion
import google_deletion

from engine import Analysis, months, yearback


# =====================================================
# 4. INITIALISATION
# =====================================================

root = Path(os.environ["ORBITE_DATA_DIR"])

root.mkdir(
    parents=True,
    exist_ok=True
)

d.BASE = root
d.DB = root / "orbite.sqlite"


# =====================================================
# 5. FILTRES COMMUNS
# =====================================================

def filters(p):

    return {
        k: str(p.get(k) or "")
        for k in [
            "region",
            "sector",
            "campaign",
            "start",
            "end"
        ]
    }


def records(c, p):

    return d.filtered(
        c,
        **filters(p)
    )


def safe(r):

    return dict(r)


# =====================================================
# 6. KPI GOOGLE - VUE D'ENSEMBLE
# =====================================================

def overview_google(params):
    """
    Same read-only adapter and period as the
    dedicated Google dashboard.
    """

    return google_view.overview(
        root,
        params
    )


# =====================================================
# 7. ROUTEUR PRINCIPAL ORBITE
# =====================================================

def run(method, p):

    # =================================================
    # QUESTIONS ADDITIONNELLES - Q01 A Q06 / V2
    # =================================================

    if method in {
        "qaHistoricalCatalog",
        "qaFilterOptions",
        "qaQuickResult",
        "qaDashboardSave",
        "qaDashboardList",
        "qaDashboardLoad",
        "qaDashboardDuplicate",
        "qaDashboardDelete",
        "qaStatistics",
        "qaExport",
        "qaDashboardExport"
    }:

        c = d.db()

        try:
            return q06.handle(
                c,
                method,
                p
            )

        finally:
            c.close()

    # =================================================
    # E-REPUTATION - IMPORTS
    # =================================================

    if method == "googleInspect":

        return er.inspect(
            p["path"],
            p["kind"]
        )

    if method == "googleImport":

        return er.import_file(
            root,
            p
        )

    if method == "googleSummary":

        return er.summary(
            root,
            p
        )

    if method == "googleExport":

        template = Path(
            os.environ.get(
                "ORBITE_MODEL_PATH",
                str(
                    Path(__file__).resolve().parent
                    / "modele_consolide2.xlsx"
                )
            )
        )

        return er.export(
            root,
            p,
            template
        )

    # =================================================
    # E-REPUTATION - SUPPRESSIONS
    # =================================================

    if method == "googleDeleteInventory":

        return google_deletion.inventory(
            root
        )

    if method == "googleDelete":

        return google_deletion.delete(
            root,
            p.get("operation"),
            p.get("confirmation"),
            p.get("period")
        )

    # =================================================
    # NPS - SUPPRESSIONS
    # =================================================

    if method == "deleteImport":

        return import_deletion.remove_confirmed(
            d,
            p.get("id"),
            p.get("confirmation")
        )

    if method == "legacyImportStatus":

        return import_deletion.legacy_status(
            d
        )

    if method == "resetLegacyNps":

        return import_deletion.reset_legacy(
            d,
            p.get("confirmation")
        )

    # =================================================
    # ETAT DU MOTEUR
    # =================================================

    if method == "health":

        c = d.db()

        try:

            return {
                "status": "ok",
                "nps_rows": c.execute(
                    "SELECT COUNT(*) FROM nps"
                ).fetchone()[0]
            }

        finally:
            c.close()

    # =================================================
    # IMPORT REFERENTIEL COMMUN NPS / GOOGLE
    # =================================================

    if method == "importReference":

        count = d.import_reference(
            p["path"]
        )

        sync = shared_reference.synchronize(
            root,
            d
        )

        return {
            "centres": count,
            "google_reference": sync
        }

    if method == "syncGoogleReference":

        return shared_reference.synchronize(
            root,
            d
        )

    # =================================================
    # IMPORT NPS
    # =================================================

    if method == "importNps":

        return d.import_nps(
            p["path"]
        )

    # =================================================
    # PUBLICATION / RESTAURATION
    # =================================================

    if method == "publish":

        return {
            "path": str(
                d.publish(p["path"])
            )
        }

    if method == "loadPublication":

        return d.load_publication(
            p["path"]
        )

    # =================================================
    # EXPORT VERBATIMS
    # =================================================

    if method == "exportVerbatims":

        c = d.db()

        try:

            rows = records(c, p)

            search = str(
                p.get("search") or ""
            ).casefold()

            exported = 0

            with open(
                p["path"],
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as f:

                w = csv.writer(
                    f,
                    delimiter=";"
                )

                w.writerow([
                    "Date",
                    "Campagne",
                    "Centre",
                    "Score",
                    "Commentaire"
                ])

                for r in rows:

                    if search in (
                        r["comment"] or ""
                    ).casefold():

                        w.writerow([
                            r["rating_date"],
                            r["appt_type"],
                            r["clinic"],
                            r["score"],
                            r["comment"]
                        ])

                        exported += 1

            return {
                "exported": exported,
                "path": p["path"]
            }

        finally:
            c.close()

    # =================================================
    # ANCIENNE METHODE EXPORT
    # =================================================

    if method == "exportEreputation":

        raise ValueError(
            "Utiliser googleExport pour générer "
            "Audika Monitoring depuis le moteur "
            "E-réputation historique."
        )

    # =================================================
    # BASE NPS / QUESTIONS
    # =================================================

    c = d.db()

    try:

        # =============================================
        # FILTRES
        # =============================================

        if method == "filters":

            centres = [
                dict(x)
                for x in c.execute(
                    """
                    SELECT code, name, region, sector
                    FROM centres
                    ORDER BY name
                    """
                )
            ]

            return {
                **google_view.filter_options(
                    root,
                    centres
                ),
                "centres": centres,
                "campaigns": [
                    x[0]
                    for x in c.execute(
                        """
                        SELECT DISTINCT appt_type
                        FROM nps
                        WHERE appt_type <> ''
                        ORDER BY appt_type
                        """
                    )
                ]
            }

        # =============================================
        # DASHBOARD NPS
        # =============================================

        if method == "npsDashboard":

            current = records(
                c,
                p
            )

            prior_filter = npsa.previous(
                p
            )

            prior = (
                records(c, prior_filter)
                if prior_filter
                else None
            )

            return npsa.dashboard(
                current,
                prior,
                prior_filter
            )

        # =============================================
        # QUESTIONS ADDITIONNELLES HISTORIQUES
        # =============================================

        if method == "questionAnalysis":

            return qa.analyze(
                records(c, p),
                p.get("search", "")
            )

        if method == "questionHistory":

            return [
                x
                for x in qa.analyze(
                    records(c, p)
                )
                if x["wording"] == p.get("wording")
            ]

        if method == "questionProfile":

            return lib.question_detail(
                c,
                p["id"]
            )

        if method == "questionResults":

            return lib.history(
                c,
                p["id"]
            )

        # =============================================
        # VUE D'ENSEMBLE
        # =============================================

        if method == "summary":

            rows = records(
                c,
                p
            )

            m = d.metrics(
                rows
            )

            m["centres"] = c.execute(
                """
                SELECT COUNT(*)
                FROM centres
                WHERE (? = "" OR region = ?)
                AND (? = "" OR sector = ?)
                """,
                (
                    p.get("region", ""),
                    p.get("region", ""),
                    p.get("sector", ""),
                    p.get("sector", "")
                )
            ).fetchone()[0]

            m.update(
                overview_google(p)
            )

            return m

        # =============================================
        # CAMPAGNES NPS
        # =============================================

        if method == "campaigns":

            rows = records(
                c,
                p
            )

            names = sorted({
                r["appt_type"]
                for r in rows
            })

            return [
                {
                    "name": name,
                    **d.metrics([
                        r
                        for r in rows
                        if r["appt_type"] == name
                    ])
                }
                for name in names
            ]

        # =============================================
        # EVOLUTION NPS
        # =============================================

        if method == "timeline":

            grouped = {}

            for r in records(c, p):

                dt = (
                    r["rating_date"]
                    if npsa.valid_score(r["score"]) is not None
                    else ""
                )[:7]

                if dt:

                    grouped.setdefault(
                        dt,
                        []
                    ).append(r)

            return [
                {
                    "month": key,
                    **d.metrics(
                        grouped[key]
                    )
                }
                for key in sorted(grouped)
            ]

        # =============================================
        # VERBATIMS
        # =============================================

        if method == "verbatims":

            search = str(
                p.get("search") or ""
            ).casefold()

            rows = [
                r
                for r in records(c, p)
                if search in (
                    r["comment"] or ""
                ).casefold()
            ]

            rows.sort(
                key=lambda r:
                    r["rating_date"] or r["send_date"],
                reverse=True
            )

            offset = max(
                0,
                int(p.get("offset") or 0)
            )

            limit = min(
                200,
                max(
                    1,
                    int(p.get("limit") or 30)
                )
            )

            return {
                "total": len(rows),
                "items": [
                    safe(x)
                    for x in rows[
                        offset:offset + limit
                    ]
                ]
            }

        # =============================================
        # EXPLORATEUR RESEAU
        # =============================================

        if method == "network":

            previous = npsa.previous(
                p
            )

            return net.build(
                c,
                records(c, p),
                (
                    records(c, previous)
                    if previous
                    else None
                ),
                p.get("region", ""),
                p.get("sector", "")
            )

        # =============================================
        # BIBLIOTHEQUE DES ENQUETES
        # =============================================

        if method == "questions":

            return lib.list_surveys(
                c,
                search=p.get("search", ""),
                campaign=p.get("campaign") or None,
                year=(
                    int(p["year"])
                    if p.get("year")
                    else None
                ),
                status=p.get("status") or None
            )

        if method == "surveyDetail":

            return lib.survey_detail(
                c,
                p["id"]
            )

        if method == "compareSurveys":

            return lib.compare(
                c,
                p["first"],
                p["second"]
            )

        if method == "surveyCreate":

            sid = lib.add_survey(
                c,
                p["campaign"],
                p["name"]
            )

            vid = lib.add_version(
                c,
                sid,
                p["version"],
                p.get("year"),
                p.get("start"),
                p.get("end"),
                status=p.get(
                    "status",
                    "preparation"
                ),
                source=p.get("source")
            )

            ids = []

            for q in p["questions"]:

                _, qid = lib.add_question(
                    c,
                    q["wording"],
                    q.get("type"),
                    q.get("options")
                )

                ids.append(qid)

            lib.set_questions(
                c,
                vid,
                ids
            )

            return {
                "survey": sid,
                "version": vid
            }

        # =============================================
        # HISTORIQUE DES IMPORTS NPS
        # =============================================

        if method == "imports":

            return import_deletion.items(
                d
            )

        # =============================================
        # METHODE INCONNUE
        # =============================================

        raise ValueError(
            "Méthode inconnue : " + method
        )

    finally:
        c.close()


# =====================================================
# 8. COMMUNICATION JSON ELECTRON / PYTHON
# =====================================================

if __name__ == "__main__":

    for line in sys.stdin:

        req = None

        try:

            req = json.loads(
                line
            )

            data = run(
                req["method"],
                req.get("params") or {}
            )

            response = {
                "id": req.get("id"),
                "data": data
            }

        except Exception as e:

            response = {
                "id": (
                    req.get("id")
                    if isinstance(req, dict)
                    else None
                ),
                "error": str(e)
            }

        sys.stdout.write(
            json.dumps(
                response,
                ensure_ascii=False,
                default=str
            ) + "\n"
        )

        sys.stdout.flush()
