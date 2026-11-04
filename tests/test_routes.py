from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from main import app, Base, engine, SessionLocal, User, Match, utcnow


def get_token(html):
    from html.parser import HTMLParser
    class CSRFParser(HTMLParser):
        val = None
        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            if tag == "input" and d.get("name") == "csrf":
                self.val = d.get("value")
    p = CSRFParser()
    p.feed(html)
    return p.val


def test_full_journey():
    Base.metadata.create_all(engine)
    with TestClient(app) as user, TestClient(app) as admin:
        csrf = get_token(user.get("/registro").text)
        res = user.post("/registro", data={"name":"Estudiante", "email":"estudiante@test.local",
                                         "password":"password-test-123", "csrf":csrf}, follow_redirects=True)
        assert res.status_code == 200 and "Estudiante" in res.text
        csrf = get_token(admin.get("/ingresar").text)
        assert admin.post("/ingresar", data={"email":"admin@test.local", "password":"admin-test-password",
                                             "csrf":csrf}, follow_redirects=True).status_code == 200
        start = (utcnow() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        csrf = get_token(admin.get("/admin").text)
        assert admin.post("/admin/partidos", data={"home_team":"Perú", "away_team":"México",
                                                 "kickoff":start, "csrf":csrf}, follow_redirects=True).status_code == 200
        with SessionLocal() as db:
            match = db.scalar(select(Match))
            match_id = match.id
        csrf = get_token(user.get("/").text)
        res = user.post(f"/pronosticar/{match_id}", data={"home_goals":2,"away_goals":1,"csrf":csrf}, follow_redirects=True)
        assert res.status_code == 200 and "Pronóstico registrado" in res.text
        csrf = get_token(user.get("/salas").text)
        res = user.post("/salas/crear", data={"name":"Sección ABCD", "csrf":csrf}, follow_redirects=True)
        assert "Sección ABCD" in res.text and "CÓDIGO DE INVITACIÓN" in res.text
        csrf = get_token(admin.get("/admin").text)
        res = admin.post(f"/admin/resultados/{match_id}", data={"home_score":2,"away_score":1,"csrf":csrf}, follow_redirects=True)
        assert res.status_code == 200
        res = user.get("/ranking")
        assert "6 pts" in res.text # exacto=5 + anticipación>24 h=1
        assert user.get("/health").json()["status"] == "ok"
        assert user.post("/admin/partidos", data={}, follow_redirects=False).status_code == 422
        # Protegido contra solicitudes sin CSRF y usuario ordinario
        assert user.post("/salas/crear", data={"name":"Malicioso", "csrf":"bad"}).status_code == 403
