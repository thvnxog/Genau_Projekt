import io

from models import Food, db


def test_health_and_food_search(client, app):
    # Prüft zuerst den einfachen Health-Check und danach die Suchfunktion für Lebensmittel.
    with app.app_context():
        db.session.add(Food(name_de="Apfel", energy_kcal=52.0))
        db.session.commit()

    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.get_json() == {"status": "ok"}

    foods_res = client.get("/foods?q=apfel&limit=5")
    assert foods_res.status_code == 200
    data = foods_res.get_json()
    assert data["items"] == [{"id": 1, "name_de": "Apfel"}]


def test_preview_route_returns_enriched_plan(monkeypatch, client):
    # Die Preview-Route soll den Plan zurückgeben, nachdem Parsing und Enrichment gelaufen sind.
    plan = {
        "schema_version": "1.0",
        "days": [
            {
                "weekday": "Montag",
                "week_index": 0,
                "menus": [
                    {
                        "menu_type": "mischkost",
                        "items": [
                            {
                                "raw_text": "Fisch",
                                "portion": {"value": 100, "unit": "g"},
                                "food_groups": [],
                                "links": {"food_group": None, "confidence": None},
                                "tags": [],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    def fake_parse_foodplan(_uploaded):
        return plan

    def fake_enrich_plan(plan_doc, *_args, **_kwargs):
        item = plan_doc["days"][0]["menus"][0]["items"][0]
        item["food_groups"] = ["fish"]
        item["links"] = {"bls_id": None, "food_group": "fish", "confidence": 1.0}
        return plan_doc, {"total_items": 1, "mapped_groups": 1}

    monkeypatch.setattr("scripts.parse_foodplan.parse_foodplan", fake_parse_foodplan)
    monkeypatch.setattr("scripts.enrich_foodplan.load_keyword_files", lambda _folder: {})
    monkeypatch.setattr("scripts.enrich_foodplan.load_json_mapping", lambda _path: ({}, {}))
    monkeypatch.setattr("scripts.enrich_foodplan.merge_keywords", lambda a, b: {})
    monkeypatch.setattr("scripts.enrich_foodplan.enrich_plan", fake_enrich_plan)

    response = client.post(
        "/api/preview",
        data={"file": (io.BytesIO(b"dummy"), "plan.xlsx"), "school_level": "P"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "preview"
    assert payload["school_level"] == "P"
    assert payload["plan"]["days"][0]["menus"][0]["items"][0]["food_groups"] == [
        "fish"
    ]


def test_preview_route_rejects_missing_or_invalid_upload(client):
    # Fehlerfälle: kein File oder falsches Dateiformat müssen sauber abgewiesen werden.
    missing_file = client.post(
        "/api/preview",
        data={"school_level": "P"},
        content_type="multipart/form-data",
    )
    assert missing_file.status_code == 400

    invalid_file = client.post(
        "/api/preview",
        data={"file": (io.BytesIO(b"dummy"), "plan.txt"), "school_level": "P"},
        content_type="multipart/form-data",
    )
    assert invalid_file.status_code == 400


def test_analyze_route_accepts_uploaded_json_file(monkeypatch, client):
    # Die Analyse-Route kann auch einen JSON-Upload direkt verarbeiten.
    def fake_eval(_plan, _rules_doc, selected_diet, school_level=None):
        return {
            "schema_version": "1.0",
            "diet": selected_diet,
            "school_level": school_level,
            "summary": {"applicable_rules": 1, "passed_rules": 1, "score": 1.0},
            "gram_hints": [],
            "rules": [],
        }

    monkeypatch.setattr(
        "scripts.evaluate_foodplan.evaluate_plan_for_diet",
        fake_eval,
    )

    payload = b'{"plan": {"schema_version": "1.0", "days": [{"week_index": 0, "menus": [{"menu_type": "mischkost", "items": [{}]}]}]}}'
    response = client.post(
        "/api/analyze",
        data={"file": (io.BytesIO(payload), "plan.json"), "school_level": "P"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["mode"] == "dual"
    assert body["mixed"]["summary"]["score"] == 1.0


def test_analyze_route_returns_dual_report_for_single_week(monkeypatch, client):
    # Ein Wochenplan erzeugt einen Dual-Report für beide Ernährungsformen.
    plan = {
        "schema_version": "1.0",
        "days": [
            {
                "weekday": "Montag",
                "week_index": 0,
                "menus": [{"menu_type": "mischkost", "items": [{}]}],
            }
        ],
    }

    def fake_eval(_plan, _rules_doc, selected_diet, school_level=None):
        return {
            "schema_version": "1.0",
            "diet": selected_diet,
            "school_level": school_level,
            "summary": {"applicable_rules": 2, "passed_rules": 1, "score": 0.5},
            "gram_hints": [],
            "rules": [],
        }

    monkeypatch.setattr(
        "scripts.evaluate_foodplan.evaluate_plan_for_diet",
        fake_eval,
    )

    response = client.post(
        "/api/analyze",
        json={"plan": plan, "school_level": "S"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "dual"
    assert payload["school_level"] == "S"
    assert payload["mixed"]["summary"]["score"] == 0.5
    assert payload["ovo_lacto_vegetarian"]["summary"]["score"] == 0.5


def test_analyze_route_returns_monthly_report_for_multiple_weeks(monkeypatch, client):
    # Mehrere Wochen werden als Monatsreport mit Wochenübersicht zurückgegeben.
    plan = {
        "schema_version": "1.0",
        "days": [
            {
                "weekday": "Montag",
                "week_index": 0,
                "week_label": "Woche 1",
                "menus": [{"menu_type": "mischkost", "items": [{}]}],
            },
            {
                "weekday": "Montag",
                "week_index": 1,
                "week_label": "Woche 2",
                "menus": [{"menu_type": "mischkost", "items": [{}]}],
            },
        ],
    }

    def fake_eval(_plan, _rules_doc, selected_diet, school_level=None):
        return {
            "schema_version": "1.0",
            "diet": selected_diet,
            "school_level": school_level,
            "summary": {"applicable_rules": 2, "passed_rules": 1, "score": 0.5},
            "gram_hints": [],
            "rules": [],
        }

    monkeypatch.setattr(
        "scripts.evaluate_foodplan.evaluate_plan_for_diet",
        fake_eval,
    )

    response = client.post(
        "/api/analyze",
        json={"plan": plan, "school_level": "P"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "monthly_dual"
    assert payload["weekly_reports"]
    assert payload["monthly_summary"]["mixed"] == {
        "applicable_rules": 4,
        "passed_rules": 2,
        "score": 0.5,
    }