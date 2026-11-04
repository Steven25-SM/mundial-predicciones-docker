"""Laboratorio 12: quiniela educativa del Mundial, FastAPI + SQLAlchemy."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import socket
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from scoring import compute_scoreboard

HERE = Path(__file__).parent
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./lab12_dev.sqlite3")
SECRET = os.getenv("SESSION_SECRET", "demo-dev-change-me")
engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
    poolclass=StaticPool if DB_URL == "sqlite:///:memory:" else None,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    home_team: Mapped[str] = mapped_column(String(80))
    away_team: Mapped[str] = mapped_column(String(80))
    kickoff: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "match_id", name="uq_user_match"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    home_goals: Mapped[int] = mapped_column(Integer)
    away_goals: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_member"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(value):
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, 260_000)
    return "pbkdf2_sha256$260000$" + salt.hex() + "$" + key.hex()


def check_password(password, encoded):
    try:
        algo, iterations, salt, digest = encoded.split("$")
        if algo != "pbkdf2_sha256":
            return False
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(computed, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def init_database():
    Base.metadata.create_all(engine)
    email = os.getenv("ADMIN_EMAIL", "admin@mundial.local").lower().strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not password:
        return
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == email))
        if admin is None:
            db.add(User(name="Administrador", email=email, password_hash=hash_password(password), is_admin=True))
            db.commit()
        elif not admin.is_admin:
            raise RuntimeError("ADMIN_EMAIL pertenece a usuario no administrador")


@asynccontextmanager
async def lifespan(_app):
    init_database()
    yield


app = FastAPI(title="MundialLab12", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET, same_site="lax", https_only=False, max_age=8 * 3600)
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
templates = Jinja2Templates(directory=str(HERE / "templates"))


def redirect(url):
    return RedirectResponse(url, status_code=303)


def msg(request, text, kind="ok"):
    request.session["flash"] = (kind, text)


def current_user(db, request):
    uid = request.session.get("user_id")
    return db.get(User, uid) if uid is not None else None


def require_auth(request, db, admin=False):
    user = current_user(db, request)
    if user is None:
        return None
    if admin and not user.is_admin:
        return None
    return user


def csrf_token(request):
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(24)
    return request.session["csrf"]


def csrf_ok(request, token):
    saved = request.session.get("csrf", "")
    return bool(saved) and hmac.compare_digest(saved, token)


def invalid_csrf():
    return HTMLResponse("Solicitud rechazada: token CSRF inválido. Recarga la página.", status_code=403)


def render(request, name, **data):
    with SessionLocal() as db:
        user = current_user(db, request)
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(request, name, {"user": user, "flash": flash,
                                                       "csrf": csrf_token(request), "node": socket.gethostname(),
                                                       "now": utcnow(), **data})


def valid_goals(h, a):
    return 0 <= h <= 30 and 0 <= a <= 30


def standings(db, users=None):
    matches = db.scalars(select(Match)).all()
    all_preds = db.scalars(select(Prediction)).all()
    group = {}
    for pred in all_preds:
        group.setdefault(pred.user_id, []).append(pred)
    users = users if users is not None else db.scalars(select(User).where(User.is_admin.is_(False))).all()
    board = [{"user": user, **compute_scoreboard(matches, group.get(user.id, []))} for user in users]
    return sorted(board, key=lambda entry: (-entry["total"], -entry["correct"], entry["user"].name.lower()))


@app.get("/health")
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unhealthy"}, status_code=503)
    return {"status": "ok", "node": socket.gethostname()}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with SessionLocal() as db:
        matches = db.scalars(select(Match).order_by(Match.kickoff, Match.id)).all()
        user = current_user(db, request)
        predictions = {}
        breakdown = {}
        if user:
            predictions = {p.match_id: p for p in db.scalars(select(Prediction).where(Prediction.user_id == user.id))}
            breakdown = compute_scoreboard(matches, list(predictions.values()))["details"]
    return render(request, "home.html", matches=matches, predictions=predictions, breakdown=breakdown)


@app.get("/registro", response_class=HTMLResponse)
def register_form(request: Request):
    return render(request, "auth.html", mode="registro")


@app.post("/registro")
def register(request: Request, name: str = Form(), email: str = Form(), password: str = Form(), csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    name, email = name.strip(), email.strip().lower()
    if not (2 <= len(name) <= 80 and 5 <= len(email) <= 190 and
            re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email) and
            8 <= len(password) <= 128):
        msg(request, "Nombre, correo o contraseña inválidos (mínimo 8 caracteres).", "error")
        return redirect("/registro")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            msg(request, "Este correo ya existe.", "error")
            return redirect("/registro")
        new_user = User(name=name, email=email, password_hash=hash_password(password), is_admin=False)
        db.add(new_user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            msg(request, "Este correo ya está registrado.", "error")
            return redirect("/registro")
        uid = new_user.id
    request.session.clear()
    request.session["user_id"] = uid
    msg(request, "Cuenta creada. ¡Bienvenido al torneo!")
    return redirect("/")


@app.get("/ingresar", response_class=HTMLResponse)
def login_form(request: Request):
    return render(request, "auth.html", mode="ingresar")


@app.post("/ingresar")
def login(request: Request, email: str = Form(), password: str = Form(), csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None or not check_password(password, user.password_hash):
            msg(request, "Credenciales incorrectas.", "error")
            return redirect("/ingresar")
        uid = user.id
    request.session.clear()
    request.session["user_id"] = uid
    msg(request, "Sesión iniciada.")
    return redirect("/")


@app.post("/salir")
def logout(request: Request, csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    request.session.clear()
    return redirect("/")


@app.post("/pronosticar/{match_id}")
def predict(request: Request, match_id: int, home_goals: int = Form(), away_goals: int = Form(), csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        match = db.get(Match, match_id)
        if match is None:
            return HTMLResponse("Partido no encontrado.", status_code=404)
        if match.kickoff <= utcnow() or match.home_score is not None:
            msg(request, "El partido está cerrado para pronósticos.", "error")
            return redirect("/")
        if not valid_goals(home_goals, away_goals):
            msg(request, "Los goles deben estar entre 0 y 30.", "error")
            return redirect("/")
        existing = db.scalar(select(Prediction).where(Prediction.user_id == user.id, Prediction.match_id == match_id))
        if existing:
            # Un pronóstico puede editarse antes del inicio; cambia su marca de tiempo.
            existing.home_goals, existing.away_goals, existing.created_at = home_goals, away_goals, utcnow()
        else:
            db.add(Prediction(user_id=user.id, match_id=match_id, home_goals=home_goals,
                              away_goals=away_goals, created_at=utcnow()))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            msg(request, "Error de concurrencia: vuelve a intentarlo.", "error")
            return redirect("/")
    msg(request, "Pronóstico registrado. Puedes modificarlo hasta el inicio del partido.")
    return redirect("/")


@app.get("/ranking", response_class=HTMLResponse)
def leaderboard(request: Request):
    with SessionLocal() as db:
        board = standings(db)
        finished = db.scalars(select(Match).where(Match.home_score.is_not(None))).all()
    return render(request, "ranking.html", board=board, finished=len(finished), room=None)


@app.get("/salas", response_class=HTMLResponse)
def rooms(request: Request):
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        ids = db.scalars(select(Membership.room_id).where(Membership.user_id == user.id)).all()
        mine = db.scalars(select(Room).where(Room.id.in_(ids)).order_by(Room.id.desc())).all() if ids else []
    return render(request, "rooms.html", mine=mine)


def unique_code(db):
    for _ in range(10):
        code = secrets.token_hex(4).upper()
        if db.scalar(select(Room).where(Room.invite_code == code)) is None:
            return code
    raise RuntimeError("No fue posible generar código de invitación")


@app.post("/salas/crear")
def create_room(request: Request, name: str = Form(), csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        name = name.strip()
        if not 3 <= len(name) <= 80:
            msg(request, "El nombre de la sala debe tener entre 3 y 80 caracteres.", "error")
            return redirect("/salas")
        room = Room(name=name, invite_code=unique_code(db), owner_id=user.id)
        db.add(room)
        db.flush()
        roomid = room.id
        db.add(Membership(room_id=roomid, user_id=user.id))
        db.commit()
    msg(request, "Sala creada. Comparte el código de invitación.")
    return redirect(f"/salas/{roomid}")


@app.post("/salas/unirse")
def join_room(request: Request, invite_code: str = Form(), csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        room = db.scalar(select(Room).where(Room.invite_code == invite_code.strip().upper()))
        if not room:
            msg(request, "Código de invitación incorrecto.", "error")
            return redirect("/salas")
        exists = db.scalar(select(Membership).where(Membership.room_id == room.id, Membership.user_id == user.id))
        if not exists:
            db.add(Membership(room_id=room.id, user_id=user.id))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
        roomid = room.id
    msg(request, "Ya perteneces a esta sala.")
    return redirect(f"/salas/{roomid}")


@app.get("/salas/{room_id}", response_class=HTMLResponse)
def room_detail(request: Request, room_id: int):
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        room = db.get(Room, room_id)
        if room is None:
            return HTMLResponse("Sala no encontrada.", status_code=404)
        membership = db.scalar(select(Membership).where(Membership.room_id == room_id, Membership.user_id == user.id))
        if membership is None:
            return HTMLResponse("No perteneces a esta sala.", status_code=403)
        member_ids = db.scalars(select(Membership.user_id).where(Membership.room_id == room_id)).all()
        members = db.scalars(select(User).where(User.id.in_(member_ids))).all()
        board = standings(db, members)
        room_name, room_code, owner_id = room.name, room.invite_code, room.owner_id
    return render(request, "ranking.html", board=board, finished=None,
                  room={"id": room_id, "name": room_name, "code": room_code, "owner_id": owner_id})


@app.post("/salas/{room_id}/renombrar")
def rename_room(request: Request, room_id: int, name: str = Form(), csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        room = db.get(Room, room_id)
        if not room:
            return HTMLResponse("No existe.", status_code=404)
        if room.owner_id != user.id:
            return HTMLResponse("Solo propietario.", status_code=403)
        if not 3 <= len(name.strip()) <= 80:
            msg(request, "Nombre de sala inválido.", "error")
        else:
            room.name = name.strip()
            db.commit()
            msg(request, "Sala renombrada.")
    return redirect(f"/salas/{room_id}")


@app.post("/salas/{room_id}/rotar")
def rotate_invite(request: Request, room_id: int, csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        room = db.get(Room, room_id)
        if room is None:
            return HTMLResponse("No existe.", status_code=404)
        if room.owner_id != user.id:
            return HTMLResponse("Solo propietario.", status_code=403)
        room.invite_code = unique_code(db)
        db.commit()
    msg(request, "Código renovado; el anterior ya no sirve.")
    return redirect(f"/salas/{room_id}")


@app.post("/salas/{room_id}/eliminar-miembro/{user_id}")
def remove_member(request: Request, room_id: int, user_id: int, csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        current = require_auth(request, db)
        if not current:
            return redirect("/ingresar")
        room = db.get(Room, room_id)
        if room is None:
            return HTMLResponse("No existe.", status_code=404)
        if room.owner_id != current.id or room.owner_id == user_id:
            return HTMLResponse("Sin permiso.", status_code=403)
        member = db.scalar(select(Membership).where(Membership.room_id == room_id, Membership.user_id == user_id))
        if member:
            db.delete(member)
            db.commit()
    msg(request, "Participante retirado.")
    return redirect(f"/salas/{room_id}")


@app.post("/salas/{room_id}/salir")
def leave_room(request: Request, room_id: int, csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        room = db.get(Room, room_id)
        if room is None:
            return HTMLResponse("No existe.", status_code=404)
        if room.owner_id == user.id:
            msg(request, "El propietario debe eliminar la sala; no puede abandonarla.", "error")
            return redirect(f"/salas/{room_id}")
        member = db.scalar(select(Membership).where(Membership.room_id == room_id, Membership.user_id == user.id))
        if member:
            db.delete(member)
            db.commit()
    msg(request, "Saliste de la sala.")
    return redirect("/salas")


@app.post("/salas/{room_id}/eliminar")
def delete_room(request: Request, room_id: int, csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        user = require_auth(request, db)
        if not user:
            return redirect("/ingresar")
        room = db.get(Room, room_id)
        if room is None:
            return HTMLResponse("No existe.", status_code=404)
        if room.owner_id != user.id:
            return HTMLResponse("Solo propietario.", status_code=403)
        for member in db.scalars(select(Membership).where(Membership.room_id == room_id)):
            db.delete(member)
        db.delete(room)
        db.commit()
    msg(request, "Sala eliminada.")
    return redirect("/salas")


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    with SessionLocal() as db:
        admin = require_auth(request, db, admin=True)
        if not admin:
            return HTMLResponse("Acceso solo para administradores. Inicia sesión con la cuenta admin.", status_code=403)
        matches = db.scalars(select(Match).order_by(Match.kickoff.desc())).all()
    return render(request, "admin.html", matches=matches)


@app.post("/admin/partidos")
def create_match(request: Request, home_team: str = Form(), away_team: str = Form(), kickoff: str = Form(), csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        admin = require_auth(request, db, admin=True)
        if not admin:
            return HTMLResponse("No autorizado.", status_code=403)
        home, away = home_team.strip(), away_team.strip()
        try:
            parsed = datetime.fromisoformat(kickoff)
            if parsed.tzinfo is not None:
                raise ValueError("Zona horaria no válida")
            # El formulario comunica UTC para evitar inconsistencias entre instancias.
        except ValueError:
            msg(request, "Fecha inválida. Usa hora UTC.", "error")
            return redirect("/admin")
        if not (2 <= len(home) <= 80 and 2 <= len(away) <= 80 and home.casefold() != away.casefold()):
            msg(request, "Los equipos deben ser diferentes y tener nombre válido.", "error")
            return redirect("/admin")
        db.add(Match(home_team=home, away_team=away, kickoff=parsed))
        db.commit()
    msg(request, "Partido de simulación creado.")
    return redirect("/admin")


@app.post("/admin/resultados/{match_id}")
def set_result(request: Request, match_id: int, home_score: int = Form(), away_score: int = Form(), csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        admin = require_auth(request, db, admin=True)
        if not admin:
            return HTMLResponse("No autorizado.", status_code=403)
        match = db.get(Match, match_id)
        if match is None:
            return HTMLResponse("No existe.", status_code=404)
        if not valid_goals(home_score, away_score):
            msg(request, "Resultado inválido: goles entre 0 y 30.", "error")
            return redirect("/admin")
        match.home_score = home_score
        match.away_score = away_score
        db.commit()
    msg(request, "Marcador publicado y puntuaciones recalculadas automáticamente.")
    return redirect("/admin")


@app.post("/admin/resultados/{match_id}/reabrir")
def reopen_match(request: Request, match_id: int, csrf: str = Form()):
    if not csrf_ok(request, csrf):
        return invalid_csrf()
    with SessionLocal() as db:
        admin = require_auth(request, db, admin=True)
        if not admin:
            return HTMLResponse("No autorizado.", status_code=403)
        match = db.get(Match, match_id)
        if match is None:
            return HTMLResponse("No existe.", status_code=404)
        match.home_score, match.away_score = None, None
        db.commit()
    msg(request, "Resultado retirado; puntajes recalculados.")
    return redirect("/admin")
